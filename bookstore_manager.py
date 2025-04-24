import sqlite3
from datetime import date

data: str = 'bookstore.db'


def checkdate(date_str: str) -> bool:
    """
    驗證日期字串是否符合 YYYY-MM-DD 格式。

    """
    return len(date_str) == 10 and date_str.count('-') == 2


def connect_db() -> sqlite3.Connection:
    """建立並返回 SQLite 資料庫連線，設置 row_factory = sqlite3.Row"""
    conn = sqlite3.connect(data)
    conn.row_factory = sqlite3.Row
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS member (
            mid TEXT PRIMARY KEY,
            mname TEXT NOT NULL,
            mphone TEXT NOT NULL,
            memail TEXT
        );

        CREATE TABLE IF NOT EXISTS book (
            bid TEXT PRIMARY KEY,
            btitle TEXT NOT NULL,
            bprice INTEGER NOT NULL,
            bstock INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sale (
            sid INTEGER PRIMARY KEY AUTOINCREMENT,
            sdate TEXT NOT NULL, -- 格式為 'YYYY-MM-DD'
            mid TEXT NOT NULL,
            bid TEXT NOT NULL,
            sqty INTEGER NOT NULL,     -- 數量
            sdiscount INTEGER NOT NULL, -- 折扣金額，單位為元
            stotal INTEGER NOT NULL    -- 總額 = (書本單價 × 數量) - 折扣
        );
    ''')
    return conn


def initialize_db(conn: sqlite3.Connection) -> None:
    """檢查並建立資料表，插入初始資料。"""
    cursor = conn.cursor()
    member = [
        ('M001', 'Alice', '0912-345678', 'alice@example.com'),
        ('M002', 'Bob', '0923-456789', 'bob@example.com'),
        ('M003', 'Cathy', '0934-567890', 'cathy@example.com')
    ]
    cursor.executemany(
        """
        INSERT OR IGNORE INTO
        member
        VALUES (?, ?, ?, ?)
        """,
        member)
    book = [
        ('B001', 'Python Programming', 600, 50),
        ('B002', 'Data Science Basics', 800, 30),
        ('B003', 'Machine Learning Guide', 1200, 20)
    ]
    cursor.executemany("INSERT OR IGNORE INTO book VALUES (?, ?, ?, ?)", book)
    sdate = date.today().strftime('%Y-%m-%d')
    sale = [
        (sdate, 'M001', 'B001', 2, 100, 1100),
        (sdate, 'M002', 'B002', 1, 50, 750),
        (sdate, 'M001', 'B003', 3, 200, 3400),
        (sdate, 'M003', 'B001', 1, 0, 600)
    ]
    cursor.executemany(
        """
        INSERT OR IGNORE INTO
        sale (sdate, mid, bid, sqty, sdiscount, stotal)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        sale
    )


def add_sale(
        conn: sqlite3.Connection,
        sdate: str,
        mid: str,
        bid: str,
        sqty: int,
        sdiscount: int
) -> tuple[bool, str]:
    """新增銷售記錄，驗證會員、書籍編號和庫存，計算總額並更新庫存。"""
    cursor = conn.cursor()
    try:
        # 驗證會員是否存在
        cursor.execute("SELECT mid FROM member WHERE mid = ?", (mid,))
        member = cursor.fetchone()
        if not member:
            return False, f"錯誤：會員編號 {mid} 無效。"

        # 驗證書籍是否存在且庫存足夠
        cursor.execute("SELECT bprice, bstock FROM book WHERE bid = ?", (bid,))
        book = cursor.fetchone()
        if not book:
            return False, f"錯誤：書籍編號 {bid} 無效。"
        if book['bstock'] < sqty:
            return False, f"錯誤：書籍庫存不足 (現有庫存: {book['bstock']})。"

        # 計算總金額
        stotal: int = (book['bprice'] * sqty) - sdiscount

        # 新增銷售記錄
        insert: str = """
        INSERT INTO sale (sdate, mid, bid, sqty, sdiscount, stotal)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        cursor.execute(insert, (sdate, mid, bid, sqty, sdiscount, stotal))

        # 更新書籍庫存
        sql_update_book: str = """
        UPDATE book SET bstock = bstock - ? WHERE bid = ?
        """
        cursor.execute(sql_update_book, (sqty, bid))

        # 提交交易
        conn.commit()
        return True, f"銷售記錄已新增！(銷售總額: {stotal:,})"

    except sqlite3.Error as e:
        # 回滾交易
        conn.rollback()
        return False, f"交易失敗：{e}"


def print_sale_report(conn: sqlite3.Connection) -> None:
    """查詢並顯示所有銷售報表，按銷售編號排序。"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            s.sid,
            s.sdate,
            m.mname,
            b.btitle,
            b.bprice,
            s.sqty,
            s.sdiscount,
            s.stotal
        FROM sale s
        JOIN member m ON s.mid = m.mid
        JOIN book b ON s.bid = b.bid
        ORDER BY s.sid
    """)
    sales = cursor.fetchall()

    if not sales:
        print(f"\n目前沒有銷售記錄。")
        return

    print("f\n==================== 銷售報表 ====================")
    for sale in sales:
        print(f"銷售 #{sale['sid']}")
        print(f"銷售編號: {sale['sid']}")
        print(f"銷售日期: {sale['sdate']}")
        print(f"會員姓名: {sale['mname']}")
        print(f"書籍標題: {sale['btitle']}")
        print("-" * 50)
        print(f"{'單價':<8}\t{'數量':<4}\t{'折扣':<6}\t{'小計'}")
        print("-" * 50)
        print(f"{sale['bprice']:<8}\t{sale['sqty']:<4}\t"
              f"{sale['sdiscount']:<6}\t{sale['stotal']:,}")
        print("-" * 50)
        print(f"銷售總額: {sale['stotal']:,}")
        print("=" * 50)
        print()


def update_sale(conn: sqlite3.Connection) -> None:
    """顯示銷售記錄列表，提示使用者輸入要更新的銷售編號和新的折扣金額，重新計算總額。"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.sid, m.mname, s.sdate
        FROM sale s
        JOIN member m ON s.mid = m.mid
        ORDER BY s.sid
    """)
    sales_list = cursor.fetchall()

    if not sales_list:
        print(f"\n目前沒有銷售記錄可以更新。")
        return

    print(f"\n======== 銷售記錄列表 ========")
    for sale in sales_list:
        print(f"{sale['sid']}. 銷售編號: {sale['sid']} - 會員: {sale['mname']} - "
              f"日期: {sale['sdate']}")
    print(f"===============================")

    while True:
        saleid: str = input("請選擇要更新的銷售編號 (輸入數字或按 Enter 取消): ")
        if not saleid:
            print(f"取消更新。")
            return
        if saleid.isdigit():
            sale_id: int = int(saleid)
            cursor.execute("SELECT sid FROM sale WHERE sid = ?", (sale_id,))
            existing_sale = cursor.fetchone()
            if existing_sale:
                break
            else:
                print(f"輸入的銷售編號不存在，請重新輸入。")
        else:
            print(f"輸入無效，請輸入數字或按 Enter 取消。")

    while True:
        ndiscount: str = input("請輸入新的折扣金額：")
        if ndiscount.isdigit():
            newdiscount: int = int(ndiscount)
            if newdiscount >= 0:
                break
            else:
                print(f"折扣金額不能為負數，請重新輸入。")
        else:
            print(f"輸入無效，請輸入數字。")

    # 查詢相關的書籍單價和數量以重新計算總額
    cursor.execute("""
        SELECT b.bprice, s.sqty
        FROM sale s
        JOIN book b ON s.bid = b.bid
        WHERE s.sid = ?
    """, (sale_id,))
    details = cursor.fetchone()

    if details:
        nstotal: int = (details['bprice'] * details['sqty']) - newdiscount
        cursor.execute(
            """
            UPDATE sale SET sdiscount = ?, stotal = ? WHERE sid = ?
            """,
            (newdiscount, nstotal, sale_id)
        )
        conn.commit()
        print(f"=> 銷售編號 {sale_id} 已更新！(銷售總額: {nstotal:,})")
    else:
        print(f"更新銷售記錄時發生錯誤，找不到相關銷售資訊。")


def delete_sale(conn: sqlite3.Connection) -> None:
    """顯示銷售記錄列表，提示使用者輸入要刪除的銷售編號，執行刪除操作並提交"""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT s.sid, m.mname, s.sdate, b.btitle
        FROM sale s
        JOIN member m ON s.mid = m.mid
        JOIN book b ON s.bid = b.bid
        ORDER BY s.sid
        """
    )
    sales_list = cursor.fetchall()

    if not sales_list:
        print(f"\n目前沒有銷售記錄可以刪除。")
        return

    print(f"\n======== 銷售記錄列表 ========")
    for sale in sales_list:
        print(f"{sale['sid']}. 銷售編號: {sale['sid']} - 會員: {sale['mname']} - "
              f"書籍: {sale['btitle']} - 日期: {sale['sdate']}")
    print(f"===============================")

    while True:
        sale_id_str: str = input(f"請選擇要刪除的銷售編號 (輸入數字或按 Enter 取消): ")
        if not sale_id_str:
            print(f"取消刪除。")
            return
        if sale_id_str.isdigit():
            sale_id_to_delete: int = int(sale_id_str)
            cursor.execute("SELECT sid FROM sale WHERE sid = ?",
                           (sale_id_to_delete,))
            existing_sale = cursor.fetchone()
            if existing_sale:
                break
            else:
                print(f"輸入的銷售編號不存在，請重新輸入。")
        else:
            print(f"=> 錯誤：請輸入有效的數字")

    cursor.execute("DELETE FROM sale WHERE sid = ?", (sale_id_to_delete,))
    conn.commit()
    print(f"=> 銷售編號 {sale_id_to_delete} 已刪除")


def main() -> None:
    """程式主流程，包含選單迴圈和各功能的呼叫"""
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM member")
        member_count = cursor.fetchone()[0]
        if member_count == 0:
            print(f"資料庫為空或首次運行，正在初始化預設資料...")
            initialize_db(conn)
        else:
            print(f"檢測到現有資料，跳過預設資料初始化。")

        while True:
            print(f"\n***************選單***************")
            print(f"1. 新增銷售記錄")
            print(f"2. 顯示銷售報表")
            print(f"3. 更新銷售記錄")
            print(f"4. 刪除銷售記錄")
            print(f"5. 離開")
            print(f"**********************************")
            choice = input(f"請選擇功能: ")
            if choice == '1':
                sdate = input(f"請輸入銷售日期 (YYYY-MM-DD): ")
                if not checkdate(sdate):
                    print(f"=> 錯誤：日期格式無效，請使用 YYYY-MM-DD 格式。")
                    continue

                mid = input(f"請輸入會員編號：")
                bid = input(f"請輸入書籍編號：")

                try:
                    sqty_str = input(f"請輸入購買數量：")
                    sqty = int(sqty_str)
                    if sqty <= 0:
                        print(f"=> 錯誤：數量必須為正整數，請重新輸入")
                        continue

                    sdiscount_str = input(f"請輸入折扣金額：")
                    sdiscount = int(sdiscount_str)
                    if sdiscount < 0:
                        print(f"=> 錯誤：折扣金額不能為負數，請重新輸入")
                        continue

                    success, message = add_sale(
                        conn, sdate,
                        mid, bid, sqty, sdiscount
                    )
                    print(f"=> {message}")

                except ValueError:
                    print(f"=> 錯誤：數量或折扣必須為整數，請重新輸入")

            elif choice == '2':
                print_sale_report(conn)
            elif choice == '3':
                update_sale(conn)
            elif choice == '4':
                delete_sale(conn)
            elif choice == '5' or choice.lower() == 'enter':
                break
            else:
                print(f"=> 請輸入有效的選項（1-5）")

    print(f"感謝使用書店管理系統！")


if __name__ == "__main__":
    main()
