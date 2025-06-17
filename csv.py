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
        columns = ', '.join(df_cleaned.columns)
        placeholders = ', '.join(['%s'] * len(df_cleaned.columns))
        insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

        for index, row in df_cleaned.iterrows():
            cursor.execute(insert_sql, tuple(row))
        
        conn.commit()
        print(f"CSV 文件 '{csv_file}' (經清洗後) 的數據已成功導入到表格 '{table_name}'。")
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
        'foodie_info':             ['user_id'],  # 若此表有 user_id 欄
        'comment_rate':            ['two_dish_rice_id', 'foodie_name_id', 'comment_rating']
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
            df_cleaned['two_dish_price'] = pd.to_numeric(
                df_cleaned['two_dish_price'], errors='coerce'
            )
            df_cleaned.dropna(subset=['two_dish_price'], inplace=True)
            # 假設價格合理範圍 0 < price < 1000
            df_cleaned = df_cleaned[
                (df_cleaned['two_dish_price'] > 0) &
                (df_cleaned['two_dish_price'] < 1000)
            ]
            print("已清洗 'two_dish_price' 欄位：轉成數字並去除異常。")

        # 處理營業時間（如有 openhour_night）
        if 'openhour_night' in df_cleaned.columns:
            df_cleaned['openhour_night'] = pd.to_datetime(
                df_cleaned['openhour_night'],
                format='%H:%M:%S',
                errors='coerce'
            ).dt.time
            df_cleaned.dropna(subset=['openhour_night'], inplace=True)
            print("已轉換 'openhour_night' 為 time 並移除無效值。")

        # 清理名稱空白
        if 'restaurant_name' in df_cleaned.columns:
            df_cleaned['restaurant_name'] = df_cleaned['restaurant_name'].str.strip()

    elif table_name == 'comment_rate':
        print("執行『食評評分』表格的特定清洗...")
        # 處理 comment_rating
        if 'comment_rating' in df_cleaned.columns:
            df_cleaned['comment_rating'] = pd.to_numeric(
                df_cleaned['comment_rating'], errors='coerce'
            )
            df_cleaned.dropna(subset=['comment_rating'], inplace=True)
            df_cleaned = df_cleaned[
                (df_cleaned['comment_rating'] >= 1) &
                (df_cleaned['comment_rating'] <= 5)
            ]
            print("已清洗 'comment_rating'：確保在 1–5 之間。")

        # 若有全文評論欄位，限制長度
        if 'comment' in df_cleaned.columns:
            df_cleaned['comment'] = df_cleaned['comment'].astype(str).str.slice(0, 500)
            print("已截斷 'comment' 最多 500 字。")

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

# --- CLI Interaction --- #

def get_table_choice():
    """Prompts user to choose a table and returns the table name."""
    print("\n請選擇要操作的數據庫表格:")
    print("  1. 兩餸飯資料 (listings_two_dish_rice)")
    print("  2. 食家資料 (foodie_info)")
    print("  3. 食評資料 (comment_rate)")
    table_map = {
        '1': 'listings_two_dish_rice',
        '2': 'foodie_info',
        '3': 'comment_rate'
    }
    while True:
        choice = input("請輸入表格代號 (1-3): ")
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
            table_name = get_table_choice()
            if table_name:
                # 初始化 tkinter
                root = tk.Tk()
                root.withdraw()  # 隱藏主視窗

                # 彈出開啟檔案對話框
                csv_file_path = filedialog.askopenfilename(
                    title=f"請選擇要導入到 '{table_name}' 的 CSV 檔案",
                    filetypes=(("CSV 檔案", "*.csv"), ("所有檔案", "*.*"))
                )
                root.destroy() # 關閉 tkinter root

                if csv_file_path: # 如果用戶選擇了檔案
                    print(f"選擇的檔案: {csv_file_path}")
                    import_csv_to_db(csv_file_path, table_name)
                else:
                    print("未選擇檔案，操作取消。")
        
        elif action_choice == '2': # 導出
            table_name = get_table_choice()
            if table_name:
                # 初始化 tkinter
                root = tk.Tk()
                root.withdraw()  # 隱藏主視窗

                # 彈出儲存檔案對話框
                csv_file_path = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    title=f"請選擇 '{table_name}' 的匯出位置和檔名"
                )
                root.destroy() # 關閉 tkinter root

                if csv_file_path: # 如果用戶選擇了路徑
                    export_db_to_csv(table_name, csv_file_path)
                else:
                    print("未選擇儲存路徑，操作取消。")

        elif action_choice == '3': # 清除
            table_name = get_table_choice()
            if table_name:
                erase_table_data(table_name)
        
        elif action_choice == '4': # 退出
            print("感謝使用，再見！")
            break
        
        else:
            print("輸入無效，請重新輸入。")
        
        input("\n按 Enter 鍵返回主菜單...")

if __name__ == "__main__":
    main()