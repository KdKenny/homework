*** 此功課為一個Python獨立程式碼，要求為至少3個django資料模型建立不少於20筆樣本資料記錄 ***

# CSV Toolkit - 為Project - 2餸飯網站管理工具

## 概述

CSV Toolkit 是一個專為Project - 2餸飯餐廳評論系統設計的數據管理工具，能夠處理餐廳資料、用戶資訊、評論數據等多種類型的CSV文件。這個工具主要用於在CSV文件和PostgreSQL數據庫之間進行數據導入、導出和清理操作。

## 主要功能

### 🔄 數據導入導出
- **CSV導入數據庫**：將清洗後的CSV數據安全導入到PostgreSQL數據庫
- **數據庫導出CSV**：將數據庫表格導出為CSV文件，方便備份和分享
- **智能衝突處理**：自動處理重複數據，支持跳過或覆蓋現有記錄

### 🗄️ 支援的數據類型

1. **餐廳資料** (`listings_two_dish_rice`)
   - 餐廳基本資訊、營業時間、價格、支付方式等

2. **管理員資料** (`adminusers_adminuser`)
   - 管理員帳號、聯絡資訊、個人描述等

3. **評論數據** (`comments_comment_rate` & `comments_commentrating`)
   - 用戶評論內容、評分、照片等
   - 評論的二次評價和互動數據

4. **用戶及聯絡人資料** (`foodie_contact`)
   - 用戶認證資訊和個人偏好設定

## 系統要求

- Python 3.7+
- PostgreSQL 數據庫
- 必要的Python套件（見(requirements.txt)）：
  - pandas
  - psycopg2-binary
  - python-dotenv
  - tkinter（GUI文件選擇）

## 使用方法

### 命令行模式

```bash
python csv_toolkit.py
```

啟動後會看到互動式選單：

```
--- CSV 數據庫工具包 ---
請選擇要執行的操作:
  1. 導入 CSV 文件到數據庫
  2. 從數據庫導出表格到 CSV 文件
  3. 清除數據庫表格的數據
  4. 退出
```

⚠️ **重要提醒**：
- 數據清除操作無法撤銷，請謹慎使用
- 建議在操作前先備份重要數據
- 確保數據庫權限設置合適

## 檔案結構

```
csv_toolkit/
├── csv_toolkit.py          # 主程式
├── db_handler.py           # 數據庫連接處理
├── requirements.txt        # 依賴套件列表
├── .env                    # 環境變數設定
├── *.csv                   # 範例數據文件
└── README.md              # 說明文檔
```

### 常見問題

1. **數據庫連接失敗**
   - 檢查 `.env` 文件設定
   - 確認PostgreSQL服務運行中
   - 驗證數據庫權限

2. **CSV格式錯誤**
   - 確保CSV文件編碼為UTF-8
   - 檢查必填欄位是否存在
   - 驗證數據格式符合預期

3. **導入失敗**
   - 查看詳細錯誤訊息
   - 檢查外鍵約束
   - 確認數據類型匹配
