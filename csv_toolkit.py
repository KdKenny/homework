import psycopg2
from psycopg2 import sql
import pandas as pd
from dotenv import load_dotenv
import os
from db_handler import connect_db # Import the connect_db function
import tkinter as tk
from tkinter import filedialog

# --- Database Interaction Functions --- #

def import_csv_to_db(csv_file, table_name):
    """Imports data from a CSV file to the specified database table after cleaning."""
    try:
        df = pd.read_csv(csv_file)
        if df.empty:
            print(f"CSV 文件 '{csv_file}' 為空，無法導入。")
            return False

        print(f"開始為表格 '{table_name}' 清洗數據...")
        df_cleaned = clean_data_for_table(df.copy(), table_name)

        if df_cleaned.empty:
            print(f"數據清洗後，CSV 文件 '{csv_file}' 無有效數s可導入到表格 '{table_name}'。")
            return False

        conn = connect_db()
        if not conn:
            print("數據庫連接失敗。")
            return False
        
        cursor = conn.cursor()
        
        # 檢查表格是否有數據
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        existing_count = cursor.fetchone()[0]
        
        if existing_count > 0:
            print(f"表格 '{table_name}' 中已有 {existing_count} 筆數據。")
            choice = input("是否清除現有數據後導入？ (y/n，預設為 n - 跳過重複數據): ").lower()
            
            if choice == 'y':
                cursor.execute(f"DELETE FROM {table_name}")
                cursor.execute(f"ALTER SEQUENCE {table_name}_id_seq RESTART WITH 1")
                print(f"已清除表格 '{table_name}' 的現有數據，並重置 ID 序列。")
            elif choice not in ['n', '']:
                print("無效輸入，導入操作已取消。")
                return False
            # 若選擇 'n' 或直接按 Enter，則繼續使用 ON CONFLICT 處理
        
        df_to_insert = df_cleaned.copy()

        # 如果導入到 'adminusers_adminuserid' 且 CSV 中存在 'id' 欄位，則移除它
        # 假設數據庫中的 'id' 是自動遞增主鍵
        if table_name == 'adminusers_adminuser' and 'id' in df_to_insert.columns:
            df_to_insert.drop(columns=['id'], inplace=True, errors='ignore')
            print(f"注意：已從導入數據中移除 'id' 欄位，以允許 '{table_name}' 表格的自動主鍵生成。")

        if df_to_insert.empty:
            if not df_cleaned.empty: # df_cleaned had data, but df_to_insert is now empty (e.g. after ID drop)
                 print(f"數據在移除 'id' 欄位後變為空，無法導入到表格 '{table_name}'。")
            else: # df_cleaned was already empty (this path might be less likely if prior check exists)
                print(f"數據清洗後，CSV 文件 '{csv_file}' 無有效數據可導入到表格 '{table_name}'。")
            return False

        columns = ', '.join(df_to_insert.columns) # Using df_to_insert
        placeholders = ', '.join(['%s'] * len(df_to_insert.columns))
        
        # 使用 ON CONFLICT DO NOTHING 來跳過重複的主鍵
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) ON CONFLICT DO NOTHING" # Using new 'columns' from df_to_insert

        inserted_count = 0 # Reset inserted_count for the new loop
        for index, row in df_to_insert.iterrows(): # Loop over df_to_insert
            cursor.execute(insert_sql, tuple(row))
            if cursor.rowcount > 0:
                inserted_count += 1
        
        conn.commit()
        print(f"CSV 文件 '{csv_file}' (經清洗後) 的數據已成功導入到表格 '{table_name}'。")
        print(f"共處理 {len(df_cleaned)} 筆記錄，成功插入 {inserted_count} 筆新數據。")
        if inserted_count < len(df_cleaned):
            print(f"跳過了 {len(df_cleaned) - inserted_count} 筆重複數據。")
        return True
    except FileNotFoundError:
        print(f"錯誤：CSV 文件 '{csv_file}' 未找到。")
        return False
    except pd.errors.EmptyDataError:
        print(f"錯誤：CSV 文件 '{csv_file}' 為空或格式不正確。")
        return False
    except Exception as e:
        print(f"導入 CSV 文件 '{csv_file}' 到表格 '{table_name}' 時發生錯誤: {e}")
        if 'conn' in locals() and conn:
            conn.rollback() # Rollback on error
        return False
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

def export_db_to_csv(table_name, csv_file):
    """Exports data from the specified database table to a CSV file."""
    conn = None
    try:
        conn = connect_db()
        if not conn:
            print("數據庫連接失敗。")
            return False

        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)

        if df.empty:
            print(f"表格 '{table_name}' 中沒有數據可供導出。")
            return False # Indicate no data to export, but not necessarily an error

        df.to_csv(csv_file, index=False, encoding='utf-8-sig') # Added encoding for better compatibility
        print(f"表格 '{table_name}' 的數據已成功導出到 '{csv_file}'。")
        return True
    except Exception as e:
        print(f"導出表格 '{table_name}' 到 CSV 時發生錯誤: {e}")
        return False
    finally:
        if conn:
            conn.close()

def clean_data_for_table(df, table_name):
    """Cleans the DataFrame based on the target table name."""
    df_cleaned = df.copy()
    print(f"執行表格 '{table_name}' 的通用清洗操作...")
    # 1. 去重
    original_rows = len(df_cleaned)
    df_cleaned.drop_duplicates(inplace=True)
    dropped = original_rows - len(df_cleaned)
    if dropped:
        print(f"移除了 {dropped} 行重複數據。")

    # 2. 必填欄位（改成實際欄位名）
    required_columns = {
        'listings_two_dish_rice': ['restaurant_name', 'two_dish_price'],
        'adminusers_adminuser': ['admin_name', 'admin_email'],  # 修正表格名稱
        'comments_comment_rate': ['restaurant_name', 'comment'], # Define actual required columns
        'comments_commentrating': ['rating', 'comment_id'] # Define actual required columns
    }
    if table_name in required_columns:
        # 只保留這些欄位都非空的行
        df_cleaned.dropna(subset=required_columns[table_name], how='any', inplace=True)

    # 通用：去除欄位名稱前後空白
    df_cleaned.columns = [c.strip() for c in df_cleaned.columns]

    # 3. 各表特定清洗
    if table_name == 'listings_two_dish_rice':
        print("執行『兩餸飯資料』表格的特定清洗...")
        # 處理 two_dish_price
        if 'two_dish_price' in df_cleaned.columns:
            # 移除貨幣符號和空白字符
            df_cleaned['two_dish_price'] = df_cleaned['two_dish_price'].astype(str).str.replace(r'[^\d.]', '', regex=True)
            # 轉換為數值，無效值設為NaN
            df_cleaned['two_dish_price'] = pd.to_numeric(df_cleaned['two_dish_price'], errors='coerce')
            # 移除價格為0或負數的記錄
            df_cleaned = df_cleaned[df_cleaned['two_dish_price'] > 0]
            print("已清洗 'two_dish_price'：移除無效價格和非正數價格。")

        # 處理所有時間相關欄位
        time_columns = ['openhour_afternoon', 'openhour_night', 'openhour_fullday', 'openhour_nightsnack',
                       'closehour_afternoon', 'closehour_night', 'closehour_fullday', 'closehour_nightsnack']
        for col in time_columns:
            if col in df_cleaned.columns:
                # 先處理字符串形式的NaN和空值
                df_cleaned[col] = df_cleaned[col].replace(['NaN', 'nan', 'NULL', 'null', ''], None)
                # 將None和NaN統一處理
                df_cleaned[col] = df_cleaned[col].where(pd.notna(df_cleaned[col]), None)
                
                # 對非None值進行時間格式轉換
                def parse_time(time_val):
                    if time_val is None or pd.isna(time_val):
                        return None
                    try:
                        # 嘗試解析時間格式
                        parsed_time = pd.to_datetime(str(time_val), format='%H:%M:%S', errors='coerce')
                        if pd.isna(parsed_time):
                            return None
                        return parsed_time.time()
                    except:
                        return None
                
                df_cleaned[col] = df_cleaned[col].apply(parse_time)
                print(f"已處理 '{col}' 並將無效值/空值轉為 None。")

        # 清理 restaurant_name
        if 'restaurant_name' in df_cleaned.columns:
            df_cleaned['restaurant_name'] = df_cleaned['restaurant_name'].str.strip()

    elif table_name == 'adminusers_adminuser':
        print("執行 'adminusers_adminuser' 表格的特定清洗...")
        # 假設與 listings 類似，主要處理字串欄位的空白
        for col in ['admin_name', 'admin_desc', 'admin_email']:  # 移除 'admin_photo'，允許空值
            if col in df_cleaned.columns:
                df_cleaned[col] = df_cleaned[col].astype(str).str.strip()
                df_cleaned[col] = df_cleaned[col].replace(['NaN', 'nan', 'NULL', 'null', ''], None)
                df_cleaned[col] = df_cleaned[col].where(pd.notna(df_cleaned[col]), None)
        print("已清洗 'adminusers_adminuser' 的字串欄位並處理空值。")

    elif table_name == 'comments_comment_rate':
        print("執行 'comments_comment_rate' 表格的特定清洗...")

        # 清洗主鍵 'id' 欄位
        if 'id' in df_cleaned.columns:
            # 如果 'id' 是 object 類型，先嘗試去除前後空格
            if df_cleaned['id'].dtype == 'object':
                df_cleaned['id'] = df_cleaned['id'].astype(str).str.strip()
            
            df_cleaned['id'] = pd.to_numeric(df_cleaned['id'], errors='coerce')
            
            initial_rows_before_id_dropna = len(df_cleaned)
            df_cleaned.dropna(subset=['id'], inplace=True) # 移除 'id' 為 NaN 的行
            dropped_count_id_nan = initial_rows_before_id_dropna - len(df_cleaned)
            
            if dropped_count_id_nan > 0:
                print(f"由於主鍵 'id' 欄位無效或轉換為數字失敗，已移除 {dropped_count_id_nan} 行。")

            # 確保 'id' 欄位存在且 DataFrame 不為空，並且所有 'id' 值都不是 NaN
            if 'id' in df_cleaned.columns and not df_cleaned.empty and df_cleaned['id'].notna().all():
                df_cleaned['id'] = df_cleaned['id'].astype(int)
            elif 'id' in df_cleaned.columns and not df_cleaned.empty and not df_cleaned['id'].notna().all():
                print("警告：'id' 欄位在移除 NaN 操作後仍包含 NaN 值，可能導致後續問題。")

        
        # 處理字串欄位，將空格、空值、NaN 轉為 None
        string_cols_to_process = {
            'to_none': ['restaurant_name', 'foodie_name', 'comment'],
            'to_empty_string': ['comment_photo1', 'comment_photo2', 'comment_photo3',
                                'comment_photo4', 'comment_photo5', 'comment_photo6']
        }

        for col in string_cols_to_process['to_none']:
            if col in df_cleaned.columns:
                df_cleaned[col] = df_cleaned[col].astype(str).str.strip()
                df_cleaned[col] = df_cleaned[col].replace(['', 'nan', 'NaN', 'NULL', 'null', ' '], None, regex=False)
                df_cleaned[col] = df_cleaned[col].apply(lambda x: None if isinstance(x, str) and x.strip() == '' else x)

        for col in string_cols_to_process['to_empty_string']:
            if col in df_cleaned.columns:
                df_cleaned[col] = df_cleaned[col].astype(str).str.strip()
                # For photo paths, convert null-like values to empty string '' instead of None
                # to satisfy potential NOT NULL constraints if an empty path is acceptable.
                df_cleaned[col] = df_cleaned[col].replace(['nan', 'NaN', 'NULL', 'null', ' '], '', regex=False)
                # Ensure actual empty strings are also just '', not None from a previous step or read_csv default
                df_cleaned[col] = df_cleaned[col].fillna('')
                df_cleaned[col] = df_cleaned[col].apply(lambda x: '' if isinstance(x, str) and x.strip() == '' else x)
                # If after stripping, it's empty, ensure it's '', not None
                df_cleaned.loc[df_cleaned[col].isnull(), col] = ''

        # 處理日期欄位
        if 'list_date' in df_cleaned.columns:
            df_cleaned['list_date'] = pd.to_datetime(df_cleaned['list_date'], errors='coerce')
        if 'edit_date' in df_cleaned.columns:
            # 處理不同的日期格式
            df_cleaned['edit_date'] = df_cleaned['edit_date'].astype(str).str.replace('/', '-')
            df_cleaned['edit_date'] = pd.to_datetime(df_cleaned['edit_date'], errors='coerce').dt.date

        # 處理布林欄位
        if 'is_published' in df_cleaned.columns:
            df_cleaned['is_published'] = df_cleaned['is_published'].astype(str).str.strip().str.upper()
            df_cleaned['is_published'] = df_cleaned['is_published'].map({'TRUE': True, 'FALSE': False, '1': True, '0': False})
            # 修正 fillna 用法，避免 Must specify a fill 'value' or 'method' 錯誤
            df_cleaned['is_published'] = df_cleaned['is_published'].where(pd.notna(df_cleaned['is_published']), None)

        # 處理評分欄位，空值轉為 None
        for col in ['restaurant_rating', 'comment_rating']:
            if col in df_cleaned.columns:
                # 先處理空格和各種空值
                df_cleaned[col] = df_cleaned[col].astype(str).str.strip()
                df_cleaned[col] = df_cleaned[col].replace(['', 'nan', 'NaN', 'NULL', 'null', ' '], None, regex=False)
                df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')
                df_cleaned[col] = df_cleaned[col].apply(lambda x: int(x) if pd.notnull(x) else None)

        # 處理 ID 欄位，空值轉為 None 或 0
        for col in ['two_dish_rice_id', 'foodie_name_id']:
            if col in df_cleaned.columns:
                # 先處理空格和各種空值
                df_cleaned[col] = df_cleaned[col].astype(str).str.strip()
                df_cleaned[col] = df_cleaned[col].replace(['', 'nan', 'NaN', 'NULL', 'null', ' '], None, regex=False)
                df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce')
                # 對於 foodie_name_id，如果是 0 就保持 0，否則轉為整數或 None
                if col == 'foodie_name_id':
                    df_cleaned[col] = df_cleaned[col].apply(lambda x: int(x) if pd.notnull(x) else 0)
                else:
                    df_cleaned[col] = df_cleaned[col].apply(lambda x: int(x) if pd.notnull(x) else None)
        
        print("已清洗 'comments_comment_rate' 的欄位並處理空值。")

        # 修改：如果 foodie_name 清洗後為 None，將其替換為 "AnonymousUser"
        # 而不是移除該行，以滿足 NOT NULL 約束。
        if 'foodie_name' in df_cleaned.columns:
            # 確保 foodie_name 是字串類型，以便進行 .fillna()
            df_cleaned['foodie_name'] = df_cleaned['foodie_name'].astype(str)
            # 將之前處理過的 None (可能來自 np.nan 或空字串) 替換為 "AnonymousUser"
            # 也要處理 pandas 讀取 CSV 時可能直接將空值讀為空字串的情況
            df_cleaned['foodie_name'] = df_cleaned['foodie_name'].replace(['None', 'nan', 'NaN', 'NULL', 'null', ''], pd.NA, regex=False).fillna('AnonymousUser')
            # 再次確保沒有空字串殘留，如果上一步的 pd.NA 處理後仍有空字串，也換成 AnonymousUser
            df_cleaned.loc[df_cleaned['foodie_name'].str.strip() == '', 'foodie_name'] = 'Guest'
            print(f"已將 'foodie_name' 為空的記錄值替換為 'Guest'。")

        # 調試打印：檢查 comments_comment_rate 清洗後的狀態
        print(f"DEBUG: 表格 '{table_name}' 清洗完成，準備返回。")
        if 'id' in df_cleaned.columns:
            unique_ids = df_cleaned['id'].unique().tolist()
            print(f"DEBUG: 清洗後 '{table_name}' 的 ID 列表 (共 {len(unique_ids)} 個): {unique_ids}")
            if 6 in df_cleaned['id'].values:
                print(f"DEBUG: 清洗後 '{table_name}' 中 id=6 的數據:")
                print(df_cleaned[df_cleaned['id'] == 6].to_string())
            else:
                print(f"DEBUG: 清洗後 '{table_name}' 中找不到 id=6 的數據。")
            # 新增調試：打印 foodie_name 清洗後的 ID 列表
            if 'foodie_name' in df_cleaned.columns:
                 print(f"DEBUG: 'foodie_name' 欄位清洗後，comments_comment_rate 剩餘的 ID: {df_cleaned['id'].unique().tolist()}")
        else:
            print(f"DEBUG: 清洗後 '{table_name}' 中找不到 'id' 欄位。")

        # 在返回前，將 DataFrame 中所有的 np.nan 轉換為 None，以便 psycopg2 正確處理為 SQL NULL
        df_cleaned = df_cleaned.astype(object).where(pd.notna(df_cleaned), None)
        print(f"DEBUG: 已將 '{table_name}' 中的 np.nan 全局轉換為 None。")
        # 重新打印 id=6 的數據，檢查 NaN 是否已變為 None
        if table_name == 'comments_comment_rate' and 'id' in df_cleaned.columns and 6 in df_cleaned['id'].values:
            print(f"DEBUG: 全局轉換 None 後，'{table_name}' 中 id=6 的數據:")
            print(df_cleaned[df_cleaned['id'] == 6].to_string())

    elif table_name == 'comments_commentrating':
        print("執行 'comments_commentrating' 表格的特定清洗...")
        string_cols_to_strip_and_none = ['rater_name']
        for col in string_cols_to_strip_and_none:
            if col in df_cleaned.columns:
                df_cleaned[col] = df_cleaned[col].astype(str).str.strip().replace(['', 'nan', 'NaN', 'NULL', 'null'], None, regex=False)

        if 'created_date' in df_cleaned.columns:
            df_cleaned['created_date'] = pd.to_datetime(df_cleaned['created_date'], errors='coerce')

        for col in ['rater_id', 'rating', 'comment_id']:
            if col in df_cleaned.columns:
                df_cleaned[col] = pd.to_numeric(df_cleaned[col], errors='coerce').apply(lambda x: int(x) if pd.notnull(x) and x != '' else None)
        
        # 新增調試：打印 comments_commentrating 清洗後的 comment_id 列表
        if 'comment_id' in df_cleaned.columns:
            print(f"DEBUG: 清洗後 'comments_commentrating' 的 comment_id 列表: {df_cleaned['comment_id'].unique().tolist()}")
            
        print("已清洗 'comments_commentrating' 的欄位並處理空值。")

    else:
        print(f"警告：未為表格 '{table_name}' 定義特定清洗邏輯，僅執行通用步驟。")

    print(f"表格 '{table_name}' 清洗完成，剩餘 {len(df_cleaned)} 行。")
    return df_cleaned


def erase_table_data(table_name):
    """Erases all data from the specified table after confirmation."""
    conn = None
    cursor = None
    confirm_phrase = f"確認清除{table_name}"
    print(f"\n警告：此操作將會永久刪除表格 '{table_name}' 中的所有數據！")
    print(f"此操作無法撤銷。")
    user_confirmation = input(f"如果確定要清除表格 '{table_name}' 的所有數據，請輸入以下文字進行確認 '{confirm_phrase}': ")

    if user_confirmation != confirm_phrase:
        print("確認失敗，操作已取消。")
        return False
    
    # Django 環境下，密碼驗證應使用 Django 的用戶認證系統
    # CLI 環境下，可以使用 getpass 獲取密碼，但這裡為了簡化，先跳過實際的密碼驗證
    # password = getpass.getpass(prompt=f"請輸入管理員密碼以授權清除操作: ")
    # if password != "your_admin_password": # 實際應用中應從安全配置讀取或更複雜驗證
    #     print("密碼錯誤，操作已取消。")
    #     return False

    try:
        conn = connect_db()
        if not conn:
            print("數據庫連接失敗。")
            return False
        cursor = conn.cursor()
        
        # 檢查表格是否存在 (可選，但更安全)
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);", (table_name,))
        if not cursor.fetchone()[0]:
            print(f"表格 '{table_name}' 不存在。")
            return False
            
        sql = f"DELETE FROM {table_name}" # 或者 TRUNCATE TABLE {table_name} 以獲得更好性能，但 TRUNCATE 可能有不同事務行為
        cursor.execute(sql)
        conn.commit()
        print(f"表格 '{table_name}' 的所有數據已成功清除。")
        return True
    except Exception as e:
        print(f"清除表格 '{table_name}' 數據時發生錯誤: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def import_export_comments(action):
    """Handles import, export, and erase operations for comments data (both tables)."""
    comment_tables = ['comments_comment_rate', 'comments_commentrating']
    # For erase operation, we need to reverse the order due to foreign key constraints
    erase_order_tables = ['comments_commentrating', 'comments_comment_rate']
    
    if action == 'import':
        print("\n評論數據導入操作:")
        # For import, use the original order to respect foreign key dependencies
        for table in comment_tables:
            print(f"\n正在處理表格: {table}")
            root = tk.Tk()
            root.withdraw()
            csv_file_path = filedialog.askopenfilename(
                title=f"請選擇要導入到 '{table}' 的 CSV 檔案",
                filetypes=(("CSV 檔案", "*.csv"), ("所有檔案", "*.*"))
            )
            root.destroy()
            if csv_file_path:
                print(f"選擇的檔案: {csv_file_path}")
                import_csv_to_db(csv_file_path, table)
            else:
                print(f"未選擇 '{table}' 的檔案，跳過此表格。")
    
    elif action == 'export':
        print("\n評論數據導出操作:")
        for table in comment_tables:
            print(f"\n正在處理表格: {table}")
            root = tk.Tk()
            root.withdraw()
            csv_file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title=f"請選擇 '{table}' 的匯出位置和檔名"
            )
            root.destroy()
            if csv_file_path:
                export_db_to_csv(table, csv_file_path)
            else:
                print(f"未選擇 '{table}' 的儲存路徑，跳過此表格。")
    
    elif action == 'erase':
        print("\n評論數據清除操作:")
        print("警告：此操作將清除所有評論相關表格的數據！")
        confirm = input("確定要繼續嗎？(y/n): ").lower()
        if confirm == 'y':
            # Use erase_order_tables to respect foreign key constraints
            for table in erase_order_tables:
                print(f"\n正在清除表格: {table}")
                erase_table_data(table)
        else:
            print("操作已取消。")
    
    else:
        print(f"未知操作: {action}")

# --- CLI Interaction --- #

def get_table_choice(action_description="操作"):
    """Prompts user to choose a table or table group and returns the choice."""
    print(f"\n請選擇要{action_description}的數據庫表格或數據組:")
    print("  1. 兩餸飯資料 (listings_two_dish_rice)")
    print("  2. 管理員用戶資料 (adminusers_adminuser)")
    print("  3. 評論數據 (comments_comment_rate & comments_commentrating)")
    table_map = {
        '1': 'listings_two_dish_rice',
        '2': 'adminusers_adminuser',
        '3': 'comments_data'  # 特殊標識符，表示評論數據組
    }
    while True:
        choice = input("請輸入代號 (1-3): ")
        if choice in table_map:
            return table_map[choice]
        else:
            print("輸入無效，請重新輸入。")

def main():
    """Main function to run the CSV toolkit CLI."""
    while True:
        print("\n--- CSV 數據庫工具包 ---")
        print("請選擇要執行的操作:")
        print("  1. 導入 CSV 文件到數據庫")
        print("  2. 從數據庫導出表格到 CSV 文件")
        print("  3. 清除數據庫表格的數據")
        print("  4. 退出")
        
        action_choice = input("請輸入操作代號 (1-4): ")

        if action_choice == '1': # 導入
            selected_item = get_table_choice(action_description="導入")
            if selected_item == 'comments_data':
                import_export_comments(action='import')
            elif selected_item:
                root = tk.Tk()
                root.withdraw()
                csv_file_path = filedialog.askopenfilename(
                    title=f"請選擇要導入到 '{selected_item}' 的 CSV 檔案",
                    filetypes=(("CSV 檔案", "*.csv"), ("所有檔案", "*.*"))
                )
                root.destroy()
                if csv_file_path:
                    print(f"選擇的檔案: {csv_file_path}")
                    import_csv_to_db(csv_file_path, selected_item)
                else:
                    print("未選擇檔案，操作取消。")
        
        elif action_choice == '2': # 導出
            selected_item = get_table_choice(action_description="導出")
            if selected_item == 'comments_data':
                import_export_comments(action='export')
            elif selected_item:
                root = tk.Tk()
                root.withdraw()
                csv_file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    title=f"請選擇 '{selected_item}' 的匯出位置和檔名"
                )
                root.destroy()
                if csv_file_path:
                    export_db_to_csv(selected_item, csv_file_path)
                else:
                    print("未選擇儲存路徑，操作取消。")

        elif action_choice == '3': # 清除
            selected_item = get_table_choice(action_description="清除")
            if selected_item == 'comments_data':
                import_export_comments(action='erase')
            elif selected_item:
                erase_table_data(selected_item)
        
        elif action_choice == '4': # 退出
            print("感謝使用，再見！")
            break
        
        else:
            print("輸入無效，請重新輸入。")
        
        input("\n按 Enter 鍵返回主菜單...")

if __name__ == "__main__":
    main()