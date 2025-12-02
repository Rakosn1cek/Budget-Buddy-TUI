import sqlite3
import datetime
import math
import os 
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn

# --- Configuration and Initialization ---

# Define the absolute, FIXED location where the data files live
DATA_DIR = os.path.expanduser('~/Budget-Buddy-TUI')

# Define the databases using the fixed path
DATABASE_EXPENSES = os.path.join(DATA_DIR, 'expenses.db')
DATABASE_SETTINGS = os.path.join(DATA_DIR, 'settings.db')

CONSOLE = Console()

# List of categories that cannot be deleted to ensure system integrity.
PROTECTED_CATEGORIES = [
    "Uncategorized", 
    "Salary", 
    "Bills", 
    "Savings Transfer", 
    "Rent", 
    "Food", 
    "Subscriptions", 
    "Online Shopping", 
    "Household"
]

# --- Utility Functions for TUI Control ---

def show_temporary_view(title, content):
    """
    Clears the screen, displays a specific piece of content, waits for input.
    """
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel(f"[bold magenta]{title}[/bold magenta]", border_style="magenta"))
    CONSOLE.print(content)
    input("\nPress Enter to return to the menu...")

def initialize_db():
    """Initializes the database tables."""
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # 1. EXPENSE Database Setup
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    cursor_exp.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            type TEXT NOT NULL
        )
    """)
    conn_exp.commit()
    conn_exp.close()

    # 2. SETTINGS Database Setup
    conn_set = sqlite3.connect(DATABASE_SETTINGS)
    cursor_set = conn_set.cursor()

    # Table for Savings Goal
    cursor_set.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Table for Recurring Templates
    cursor_set.execute("""
        CREATE TABLE IF NOT EXISTS recurring_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, 
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            due_day INTEGER
        )
    """)
    
    # Table for User Defined Categories
    cursor_set.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY
        )
    """)
    
    # Default categories
    for cat in PROTECTED_CATEGORIES:
        try:
            cursor_set.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
        except sqlite3.IntegrityError:
            pass 

    conn_set.commit()
    conn_set.close()

def migrate_recurring_templates_schema():
    """Migrates recurring_templates to allow duplicate names."""
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE recurring_templates RENAME TO recurring_templates_old")
        cursor.execute("""
            CREATE TABLE recurring_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                due_day INTEGER
            )
        """)
        cursor.execute("""
            INSERT INTO recurring_templates (id, name, amount, category, description, due_day)
            SELECT id, name, amount, category, description, due_day FROM recurring_templates_old
        """)
        cursor.execute("DROP TABLE recurring_templates_old")
        conn.commit()
    except:
        pass
    finally:
        conn.close()

def db_check_and_migrate():
    """Checks integrity and runs migrations."""
    migrate_recurring_templates_schema()

    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    try:
        cursor_exp.execute("SELECT type FROM transactions LIMIT 1")
    except sqlite3.OperationalError:
        CONSOLE.print("[yellow]Database migration needed: Adding 'type' column.[/yellow]")
        cursor_exp.execute("ALTER TABLE transactions ADD COLUMN type TEXT DEFAULT 'expense'")
        cursor_exp.execute("UPDATE transactions SET type = 'expense' WHERE type IS NULL")
        CONSOLE.print("[green]Migration complete: 'type' column added.[/green]")
        conn_exp.commit()
    conn_exp.close()
    
    conn_set = sqlite3.connect(DATABASE_SETTINGS)
    cursor_set = conn_set.cursor()
    try:
        cursor_set.execute("SELECT due_day FROM recurring_templates LIMIT 1")
    except sqlite3.OperationalError:
        CONSOLE.print("[yellow]Settings migration: Adding 'due_day' column.[/yellow]")
        cursor_set.execute("ALTER TABLE recurring_templates ADD COLUMN due_day INTEGER DEFAULT 1")
        CONSOLE.print("[green]Migration complete: 'due_day' added.[/green]")
        conn_set.commit()
    conn_set.close()

# --- Core Data Fetching Functions ---

def get_financial_summary():
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='income'")
    total_income = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense'")
    total_expenses_raw = cursor.fetchone()[0] or 0.0
    total_expenses = total_expenses_raw * -1 
    net_balance = total_income + total_expenses
    conn.close()
    return total_income, total_expenses, net_balance

def get_savings_goal():
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    goal_target = cursor.execute("SELECT value FROM settings WHERE key='goal_target'").fetchone()
    current_saved = cursor.execute("SELECT value FROM settings WHERE key='current_saved'").fetchone()
    conn.close()
    return (float(goal_target[0]) if goal_target else 0.0, float(current_saved[0]) if current_saved else 0.0)

def get_last_n_transactions(n=10):
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    # Fetch all relevant columns including 'description' (index 3)
    cursor.execute("SELECT id, amount, category, description, date, type FROM transactions ORDER BY date DESC, id DESC LIMIT ?", (n,))
    transactions = cursor.fetchall()
    conn.close()
    return transactions

def get_paginated_transactions(page=1, page_size=10):
    """Fetches transactions for a specific page."""
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()

    # Get total count
    cursor.execute("SELECT COUNT(*) FROM transactions")
    total_count = cursor.fetchone()[0]

    # Calculate offset and limit
    offset = (page - 1) * page_size
    
    # Fetch paginated transactions
    sql = "SELECT id, amount, category, description, date, type FROM transactions ORDER BY date DESC, id DESC LIMIT ? OFFSET ?"
    cursor.execute(sql, (page_size, offset))
    transactions = cursor.fetchall()
    conn.close()
    
    total_pages = math.ceil(total_count / page_size) if page_size > 0 else 1
    
    return transactions, total_count, total_pages


def fetch_category_names():
    """Fetches list of all category names from the database, sorted alphabetically."""
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories ORDER BY name ASC")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

def get_categories_with_ids():
    """Fetches category names and assigns a sequential display ID."""
    category_names = fetch_category_names()
    categories_with_ids = []
    for i, name in enumerate(category_names, 1):
        categories_with_ids.append((i, name)) # (id, name)
    return categories_with_ids

def get_category_name_by_id(cat_id):
    """Utility to map display ID back to category name."""
    categories = get_categories_with_ids()
    try:
        cat_id = int(cat_id)
        for i, name in categories:
            if i == cat_id:
                return name
        return None
    except ValueError:
        return None

# --- Display Functions ---

def display_dashboard(message=""):
    # Clear screen before render
    os.system('cls' if os.name == 'nt' else 'clear')
    
    now = datetime.datetime.now()
    header_date = now.strftime("%A, %d %b %Y | %H:%M")
    
    header_content = Text(f"BUDGET BUDDY TUI | {header_date}", style="bold white on purple")
    CONSOLE.print(Panel(header_content, title_align="left", border_style="purple"))

    total_income, total_expenses, net_balance = get_financial_summary()
    recent_transactions = get_last_n_transactions(10)
    
    # Financial Overview
    balance_style = "bold green" if net_balance >= 0 else "bold red"
    overview_text = Text()
    overview_text.append("Total Income:  ", style="green")
    overview_text.append(f"+£{total_income:,.2f}\n", style="bold green")
    overview_text.append("Total Expenses: ", style="red")
    overview_text.append(f"£{total_expenses:,.2f}\n", style="bold red")
    overview_text.append("NET BALANCE:    ", style="cyan")
    overview_text.append(f"£{net_balance:,.2f}", style=balance_style)
    
    overview_panel = Panel(overview_text, title="FINANCIAL OVERVIEW (All Time)", border_style="cyan", width=87)

    # Savings Goal
    goal_target, current_saved = get_savings_goal()
    savings_panel_content = None 
    if goal_target > 0:
        progress_val = (current_saved / goal_target) * 100 if goal_target > 0 else 0
        progress_val = min(progress_val, 100)
        goal_target_str = f"£{goal_target:,.2f}"
        current_saved_str = f"£{current_saved:,.2f}"
        progress_bar = Progress(
            TextColumn(f"Saved: {current_saved_str} / {goal_target_str}"),
            BarColumn(bar_width=20, style="yellow", complete_style="bold green"),
            TextColumn(f"{progress_val:.0f}%", style="bold yellow"),
            console=CONSOLE,
            transient=True
        )
        task_id = progress_bar.add_task("[bold cyan]Saving...", total=goal_target)
        progress_bar.update(task_id, completed=current_saved)
        progress_table = progress_bar.make_tasks_table(progress_bar.tasks)
        final_line = Text(f"\nGoal Progress: {progress_val:.0f}%", style="bold green")
        savings_panel_content = Group(progress_table, final_line)
    else:
        savings_panel_content = Text("[yellow]No savings goal set. Use option 8 to set one![/yellow]")
    savings_panel = Panel(savings_panel_content, title="SAVINGS GOAL", border_style="yellow", width=87)

    # Menu
    menu_table = Table.grid(padding=(0, 1))
    menu_table.add_column()
    menu_table.add_column()
    menu_options = [
        ("1. Add Transaction", "bold green"),
        ("2. View Transaction History (Card View)", "bold cyan"), # Updated Menu Text
        ("3. Filter by Category", "bold magenta"),
        ("4. Weekly Summary", "yellow"),
        ("5. Monthly Detailed Summary", "yellow"),
        ("6. Upcoming Calendar", "bright_blue"),
        ("7. Delete Transaction", "bold red"),
        ("8. Set Savings Goal", "yellow"),
        ("9. Add to Savings", "green"),
        ("10. Recurring Templates", "orange1"),
        ("11. Apply Recurring Payment", "green"),
        ("12. Exit Application", "bold white"),
        ("13. Manage Categories", "bold yellow")
    ]
    for i, (text, style) in enumerate(menu_options):
        parts = text.split(". ", 1)
        menu_table.add_row(f"[bold white]{parts[0]}.[/bold white]", Text(parts[1], style=style))
    menu_panel = Panel(menu_table, title="MENU", border_style="magenta", width=87)
    
    # Recent Transactions
    recent_tx_table = Table(show_header=True, header_style="bold green", show_lines=False, padding=(0, 1))
    recent_tx_table.add_column("ID", style="dim", min_width=3, width=4)
    recent_tx_table.add_column("Date (MM-DD)", width=8)
    # --- MODIFICATION START ---
    # Changed header from "Category" to "Description" and increased max_width
    recent_tx_table.add_column("Description", max_width=27, overflow="fold") 
    # --- MODIFICATION END ---
    recent_tx_table.add_column("Amount", justify="right", width=10)

    if not recent_transactions:
        recent_tx_table.add_row(Text("", style="dim"), Text("[yellow]No recent transactions.[/yellow]", style="yellow"), Text("", style="cyan"), Text("", justify="right"))
    else:
        # --- MODIFICATION START ---
        # Unpack all fields, using 'description' (index 3) in the table row
        for tid, amount, category, description, date_str, t_type in recent_transactions:
            # Use description, but fallback to category if description is None or empty
            display_name = description if description else category
            # --- MODIFICATION END ---
            
            amount_display = f"£{amount:,.0f}"
            style = "bold green" if t_type == 'income' else "bold red"
            if t_type == 'income': amount_display = "+" + amount_display
            else: amount_display = "-" + amount_display
            
            try:
                date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                display_date = date_obj.strftime("%m-%d")
            except (ValueError, TypeError):
                display_date = str(date_str)

            # --- MODIFICATION START ---
            # Pass the display_name (description) to the table
            recent_tx_table.add_row(str(tid), display_date, display_name, Text(amount_display, style=style))
            # --- MODIFICATION END ---

    recent_tx_panel = Panel(recent_tx_table, title="LAST 10 TRANSACTIONS", border_style="green", width=87)
    
    CONSOLE.print(overview_panel)
    CONSOLE.print(savings_panel)
    CONSOLE.print(menu_panel)
    CONSOLE.print(recent_tx_panel) 

    if message:
        message_content = Text.from_markup(message)
        CONSOLE.print(Panel(message_content, title="NOTIFICATION", border_style="yellow", width=87))

    return input("\nSelect an option (1-13): ")

# --- Input Functions ---

def validate_date(date_str):
    if not date_str: return datetime.datetime.now().date()
    try:
        return datetime.datetime.strptime(date_str, "%d-%m-%Y").date()
    except ValueError:
        return None

# --- Transaction Logic ---

def add_transaction():
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold magenta]Add New Transaction[/bold magenta]", border_style="magenta"))
    
    while True:
        t_type = input("Type [I]ncome or [E]xpense: ").lower()
        if t_type in ('i', 'income'): transaction_type = 'income'; break
        elif t_type in ('e', 'expense'): transaction_type = 'expense'; break
        CONSOLE.print("[bold red]Invalid type. Enter 'I' or 'E'.[/bold red]")

    while True:
        try:
            amount = float(input(f"Enter amount (£): "))
            if amount <= 0: 
                CONSOLE.print("[bold red]Positive amount required.[/bold red]")
                continue
            break
        except ValueError: CONSOLE.print("[bold red]Invalid number.[/bold red]")

    # Category Selection by ID
    categories_with_ids = get_categories_with_ids()
    
    cat_table = Table(title="Available Categories", show_header=True, header_style="bold cyan")
    cat_table.add_column("ID", style="yellow", width=4)
    cat_table.add_column("Name", style="cyan")
    
    for cat_id, name in categories_with_ids:
        cat_table.add_row(str(cat_id), name)
        
    CONSOLE.print(cat_table)
    
    while True:
        cat_input = input("Enter Category ID (or C to cancel): ").strip()
        if cat_input.upper() == 'C': return "[yellow]Transaction entry cancelled.[/yellow]"
        
        category = get_category_name_by_id(cat_input)
        
        if category:
            break
        else:
            # Check if user wants to add a new category by name if input isn't a valid ID
            if input(f"ID '{cat_input}' not found. Add a NEW category with name '{cat_input}'? (y/n): ").lower() == 'y':
                add_category_to_db(cat_input)
                category = cat_input
                break
            else:
                CONSOLE.print("[bold red]Invalid ID or not adding a new category. Please try again or C to cancel.[/bold red]")
                continue

    description = input("Enter description: ").strip()
    default_date = datetime.datetime.now().strftime("%d-%m-%Y")
    
    while True:
        date_input = input(f"Enter Date (DD-MM-YYYY, default: {default_date}): ").strip()
        dt_obj = validate_date(date_input)
        if dt_obj: 
            date_str = dt_obj.strftime("%Y-%m-%d")
            display_date = dt_obj.strftime("%d-%m-%Y")
            break
        CONSOLE.print("[bold red]Invalid format (DD-MM-YYYY).[/bold red]")

    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                   (amount, category, description, date_str, transaction_type))
    conn.commit()
    conn.close()
    return f"[bold green]Recorded {transaction_type.upper()}: £{amount:,.2f} ({category}) on {display_date}.[/bold green]"

def view_transactions_table(filter_query=None, title="Recent Expenses"):
    """
    Renders transactions in a single table (used for filter/delete helper views).
    Kept for delete_transaction use.
    """
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    sql = "SELECT id, amount, category, description, date, type FROM transactions ORDER BY date DESC, id DESC LIMIT 50"
    params = ()
    if filter_query:
        sql = "SELECT id, amount, category, description, date, type FROM transactions WHERE category LIKE ? ORDER BY date DESC, id DESC"
        params = ('%' + filter_query + '%',)
        title = f"Filtered: '{filter_query}'"
    
    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows: return Group(Text("[yellow]No transactions found.[/yellow]")), title

    table = Table(title=f"History: {title}", title_style="bold yellow", show_header=True, header_style="bold magenta", padding=(0,1))
    # Removing fixed width to allow Rich to better manage space, preventing truncation
    table.add_column("ID", style="dim", min_width=4) 
    table.add_column("Date", style="bold white", min_width=10)
    table.add_column("Category", style="cyan", min_width=15) 
    table.add_column("Description", style="white", min_width=25)
    table.add_column("Amount", style="bold", justify="right", min_width=10)

    for tid, amount, cat, desc, d_db, t_type in rows:
        try: d_disp = datetime.datetime.strptime(d_db, "%Y-%m-%d").strftime("%d-%m-%y")
        except: d_disp = d_db
        
        amt_str = f"£{amount:,.2f}"
        style = "bold green" if t_type == 'income' else "bold red"
        if t_type == 'income': amt_str = "+" + amt_str
        else: amt_str = "-" + amt_str
        
        table.add_row(str(tid), d_disp, cat, (desc or "—"), Text(amt_str, style=style))
        
    return table, title

def display_filtered_transactions_in_cards(filter_query):
    """
    NEW: Fetches filtered transactions and displays them in the non-paginated card view.
    """
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    # Fetch all transactions matching the category filter
    sql = "SELECT id, amount, category, description, date, type FROM transactions WHERE category LIKE ? ORDER BY date DESC, id DESC"
    params = ('%' + filter_query + '%',)
    cursor.execute(sql, params)
    transactions = cursor.fetchall()
    conn.close()

    title = f"Filtered: '{filter_query}'"

    if not transactions: 
        show_temporary_view(title, Text("[yellow]No transactions found matching this filter.[/yellow]"))
        return

    cards = []
    for tid, amount, cat, desc, d_db, t_type in transactions:
        try: d_disp = datetime.datetime.strptime(d_db, "%Y-%m-%d").strftime("%d %b %Y")
        except: d_disp = d_db

        style = "bold green" if t_type == 'income' else "bold red"
        
        amount_str = f"£{amount:,.2f}"
        if t_type == 'income': amount_str = "+" + amount_str
        else: amount_str = "-" + amount_str
        
        # Grid for clean left-justified card content
        card_content = Table.grid(padding=(0, 1), expand=True) 
        # Left-justify both columns for clean reading
        card_content.add_column(style="dim", justify="left", min_width=10) 
        card_content.add_column(style="bold white", justify="left")
        
        card_content.add_row("ID:", str(tid))
        card_content.add_row("Date:", d_disp)
        card_content.add_row("Category:", cat)
        card_content.add_row("Description:", desc or "—")
        card_content.add_row("Type:", t_type.capitalize())
        
        cards.append(
            Panel(
                card_content,
                title=Text(amount_str, style=style),
                title_align="right",
                border_style=style,
                width=None 
            )
        )
    
    # Display cards as a Group (stacked vertically)
    card_group = Group(*cards)
    show_temporary_view(title, card_group)

def view_transactions_paginated():
    """
    Renders transactions in a paginated card view (Option 2).
    """
    page = 1
    page_size = 10
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        
        transactions, total_count, total_pages = get_paginated_transactions(page, page_size)

        current_range_start = (page - 1) * page_size + 1
        current_range_end = min(page * page_size, total_count)

        CONSOLE.print(Panel(
            f"[bold magenta]Transaction History (Card View)[/bold magenta]", 
            subtitle=f"Page {page} of {total_pages} | Showing {current_range_start}-{current_range_end} of {total_count} total.",
            border_style="magenta"
        ))

        if not transactions:
            CONSOLE.print(Panel("[yellow]No transactions found in this range.[/yellow]"))
        else:
            cards = []
            for tid, amount, cat, desc, d_db, t_type in transactions:
                try: d_disp = datetime.datetime.strptime(d_db, "%Y-%m-%d").strftime("%d %b %Y")
                except: d_disp = d_db

                style = "bold green" if t_type == 'income' else "bold red"
                
                amount_str = f"£{amount:,.2f}"
                if t_type == 'income': amount_str = "+" + amount_str
                else: amount_str = "-" + amount_str
                
                # Use a grid within the panel for clean alignment
                card_content = Table.grid(padding=(0, 1), expand=True) 
                # Left-justify both columns for consistency with filter view
                card_content.add_column(style="dim", justify="left", min_width=10)
                card_content.add_column(style="bold white", justify="left")
                
                card_content.add_row("ID:", str(tid))
                card_content.add_row("Date:", d_disp)
                card_content.add_row("Category:", cat)
                card_content.add_row("Description:", desc or "—")
                card_content.add_row("Type:", t_type.capitalize())
                
                cards.append(
                    Panel(
                        card_content,
                        title=Text(amount_str, style=style),
                        title_align="right",
                        border_style=style,
                        width=None # Let rich console manage width
                    )
                )
            
            # Display cards as a Group (stacked vertically)
            card_group = Group(*cards)
            CONSOLE.print(card_group)
        
        # Navigation
        nav_options = []
        if page > 1:
            nav_options.append("[P]revious Page")
        if page < total_pages:
            nav_options.append("[N]ext Page")
        nav_options.append("[C]ancel / Exit")
        
        CONSOLE.print("\n" + " | ".join(nav_options), style="bold yellow")
        
        choice = input("Enter choice (P/N/C): ").upper().strip()

        if choice == 'C':
            return "[bold green]Transaction history view closed.[/bold green]"
        elif choice == 'P' and page > 1:
            page -= 1
        elif choice == 'N' and page < total_pages:
            page += 1
        else:
            if choice not in ('P', 'N'):
                 CONSOLE.print("[red]Invalid choice. Must be P, N, or C.[/red]")
                 input("Press Enter to continue...")
            elif choice == 'P' or choice == 'N': # Prevent accidental exit if P or N pressed on boundary
                 input("No more pages in that direction. Press Enter to continue...")


def delete_transaction():
    table, title = view_transactions_table(title="Delete Transaction")
    show_temporary_view(title, table)
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold red]Delete Transaction[/bold red]", border_style="red"))
    CONSOLE.print(table)
    
    while True:
        tid = input("\nEnter ID to delete (C to cancel): ").upper().strip()
        if tid == 'C': return "Deletion cancelled."
        try: 
            tid_int = int(tid)
            break
        except ValueError: CONSOLE.print("[bold red]Invalid ID.[/bold red]")
            
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cur = conn.cursor()
    cur.execute("DELETE FROM transactions WHERE id = ?", (tid_int,))
    if cur.rowcount > 0:
        conn.commit(); conn.close()
        return f"[bold green]Deleted ID {tid_int}.[/bold green]"
    conn.close()
    return f"[bold red]ID {tid_int} not found.[/bold red]"

def filter_by_category():
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel("[bold magenta]Filter[/bold magenta]", border_style="magenta"))
    # Note: Filter input remains text since it allows partial matches.
    cat = input("Enter Category Name (partial match allowed): ").strip()
    if cat:
        # Changed to use the new card view function for responsiveness
        display_filtered_transactions_in_cards(filter_query=cat)
        return f"[bold green]Filter applied: {cat}[/bold green]"
    return "[yellow]Cancelled.[/yellow]"

def get_transaction_data(start, end):
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cur = conn.cursor()
    cur.execute("SELECT amount, category, type FROM transactions WHERE date BETWEEN ? AND ?", (start, end))
    rows = cur.fetchall()
    conn.close()
    summary = {}
    for amt, cat, typ in rows:
        cat = cat.strip()
        if cat not in summary: summary[cat] = {'expense':0.0, 'income':0.0}
        if typ == 'income': summary[cat]['income'] += amt
        else: summary[cat]['expense'] += amt
    return summary

def monthly_summary():
    now = datetime.datetime.now()
    start = now.strftime("%Y-%m-01")
    end = now.strftime("%Y-%m-%d")
    data = get_transaction_data(start, end)
    
    if not data:
        show_temporary_view(f"Monthly: {now.strftime('%B %Y')}", Text("[yellow]No data.[/yellow]"))
        return

    table = Table(title=f"Monthly Breakdown: {now.strftime('%B')}", show_header=True, header_style="bold cyan")
    table.add_column("Category", width=15); table.add_column("Income", justify="right"); table.add_column("Expense", justify="right"); table.add_column("Net", justify="right")
    
    t_inc = t_exp = 0
    for cat, val in data.items():
        i, e = val['income'], val['expense']
        t_inc += i; t_exp += e
        net = i - e
        style = "bold green" if net >= 0 else "bold red"
        table.add_row(cat, f"£{i:,.2f}", f"£{e:,.2f}", Text(f"£{net:,.2f}", style=style))
    
    final_net = t_inc - t_exp
    footer = Group(table, Text("\n"+"="*40), Text.from_markup(f"[green]Income:  £{t_inc:,.2f}[/green]"), Text.from_markup(f"[red]Expense: £{t_exp:,.2f}[/red]"), Text(f"Net:     £{final_net:,.2f}", style="bold green" if final_net >=0 else "bold red"))
    show_temporary_view("Monthly Summary", footer)

def weekly_summary():
    now = datetime.datetime.now()
    start = (now - datetime.timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    end = (datetime.datetime.strptime(start, "%Y-%m-%d") + datetime.timedelta(days=6)).strftime("%Y-%m-%d")
    data = get_transaction_data(start, end)
    
    if not data:
        show_temporary_view(f"Weekly: {start} to {end}", Text("[yellow]No data.[/yellow]"))
        return

    table = Table(title="Weekly Breakdown", show_header=True, header_style="bold magenta")
    table.add_column("Category", width=15); table.add_column("Expense", justify="right"); table.add_column("Income", justify="right")
    
    t_inc = t_exp = 0
    for cat, val in data.items():
        i, e = val['income'], val['expense']
        t_inc += i; t_exp += e
        table.add_row(cat, f"£{e:,.2f}", f"£{i:,.2f}")
        
    final_net = t_inc - t_exp
    footer = Group(table, Text("\n"+"-"*40), Text.from_markup(f"[green]Income:  £{t_inc:,.2f}[/green]"), Text.from_markup(f"[red]Expense: £{t_exp:,.2f}[/red]"), Text(f"Net:     £{final_net:,.2f}", style="bold green" if final_net >=0 else "bold red"))
    show_temporary_view("Weekly Summary", footer)

# --- RECURRING & TEMPLATE FUNCTIONS ---

def get_recurring_templates():
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cur = conn.cursor()
    cur.execute("SELECT id, name, amount, category, description, due_day FROM recurring_templates ORDER BY category ASC, due_day ASC")
    rows = cur.fetchall()
    conn.close()
    return rows

def manage_recurring_templates():
    templates = get_recurring_templates()
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold orange1]Manage Recurring Templates[/bold orange1]", border_style="orange1"))
    
    if not templates:
        CONSOLE.print("[yellow]No templates.[/yellow]")
    else:
        # 1. Group templates by Category
        grouped_templates = {}
        for tid, name, amt, cat, desc, day in templates:
            cat = cat.strip() # Ensure clean key
            if cat not in grouped_templates:
                grouped_templates[cat] = []
            grouped_templates[cat].append({
                'id': tid, 
                'name': name, 
                'amount': amt, 
                'due_day': day,
            })
            
        # 2. Create Cards for each Category
        category_cards = []
        sorted_categories = sorted(grouped_templates.keys())
        
        for category in sorted_categories:
            template_list = grouped_templates[category]
            
            # Inner Table for the specific category
            inner_table = Table(show_header=True, header_style="bold dim", show_lines=False, padding=(0, 1), box=None)
            
            # Defining the structure that is mobile-friendly
            inner_table.add_column("ID", width=4, style="cyan")
            inner_table.add_column("Day", width=4, justify="center", style="yellow")
            inner_table.add_column("Name", min_width=15, style="bold white")
            inner_table.add_column("Amount", justify="right", style="red")
            
            for t in template_list:
                amount_str = f"£{t['amount']:,.2f}"
                inner_table.add_row(
                    str(t['id']),
                    str(t['due_day']),
                    t['name'],
                    amount_str
                )

            category_cards.append(
                Panel(
                    inner_table,
                    title=f"[bold orange1]{category} ({len(template_list)})[/bold orange1]",
                    title_align="left", # Left justified as requested
                    border_style="orange1",
                    width=None 
                )
            )
            
        CONSOLE.print(Group(*category_cards))
        
        CONSOLE.print("\n[yellow]NOTE: Since Name is not unique, use the ID when deleting or applying a template.[/yellow]")
        
    CONSOLE.print("\n[1] Add New | [2] Delete | [C] Cancel")
    ch = input("Choice: ").upper().strip()
    if ch == '1': return add_recurring_template()
    if ch == '2': return delete_recurring_template(templates)
    return "Cancelled."

def add_recurring_template():
    count = 0
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        CONSOLE.print(Panel(f"[bold green]Add Recurring Template ({count} added)[/bold green]"))
        name = input("Name (or C to stop): ").strip()
        if name.upper() == 'C': break
        
        try: amt = float(input("Amount (£): ")); day = int(input("Due Day (1-31): "))
        except: CONSOLE.print("[red]Invalid input.[/red]"); continue
        
        cat = input("Category: ").strip() or "Uncategorized"
        desc = input("Desc: ").strip()
        
        conn = sqlite3.connect(DATABASE_SETTINGS)
        cur = conn.cursor()
        # Insert allowing duplicates (no UNIQUE constraint on name)
        cur.execute("INSERT INTO recurring_templates (name, amount, category, description, due_day) VALUES (?, ?, ?, ?, ?)",
                   (name, amt, cat, desc, day))
        conn.commit(); conn.close()
        count += 1
        CONSOLE.print(f"[green]Added '{name}'[/green]")
        if input("Add another? (y/n): ").lower() != 'y': break
    return f"Added {count} templates."

def delete_recurring_template(templates):
    os.system('cls' if os.name == 'nt' else 'clear')
    if not templates: return "[yellow]None to delete.[/yellow]"
    
    CONSOLE.print(Panel("[bold red]Delete Template[/bold red]"))
    # The list of templates would ideally be shown here again for reference, 
    # but we rely on the user having checked Option 10 first.
    
    while True:
        tid = input("ID to delete (C to cancel): ").upper().strip()
        if tid == 'C': return "Cancelled."
        try: tid_int = int(tid); break
        except: pass
        
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cur = conn.cursor()
    cur.execute("DELETE FROM recurring_templates WHERE id = ?", (tid_int,))
    if cur.rowcount > 0:
        conn.commit(); conn.close()
        return f"[green]Deleted ID {tid_int}.[/green]"
    conn.close()
    return "[red]ID not found.[/red]"

def apply_recurring_template():
    templates = get_recurring_templates()
    if not templates: return "[red]No templates found.[/red]"
    
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold green]Apply Recurring Payment[/bold green]", border_style="green"))
    
    # 1. Group templates by Category and create the t_map for selection
    grouped_templates = {}
    t_map = {}
    for tid, name, amt, cat, desc, day in templates:
        cat = cat.strip()
        t_map[tid] = (name, amt, cat, desc) # Create map for selection later
        if cat not in grouped_templates:
            grouped_templates[cat] = []
        grouped_templates[cat].append({
            'id': tid, 
            'name': name, 
            'amount': amt, 
            'due_day': day,
        })
        
    # 2. Create Cards for each Category (display)
    category_cards = []
    sorted_categories = sorted(grouped_templates.keys())
    
    for category in sorted_categories:
        template_list = grouped_templates[category]
        
        # Inner Table for the specific category
        inner_table = Table(show_header=True, header_style="bold dim", show_lines=False, padding=(0, 1), box=None)
        
        inner_table.add_column("ID", width=4, style="cyan")
        inner_table.add_column("Day", width=4, justify="center", style="yellow")
        inner_table.add_column("Name", min_width=15, style="bold white")
        inner_table.add_column("Amount", justify="right", style="red")
        
        for t in template_list:
            amount_str = f"£{t['amount']:,.2f}"
            inner_table.add_row(str(t['id']), str(t['due_day']), t['name'], amount_str)

        category_cards.append(
            Panel(
                inner_table,
                title=f"[bold green]{category} ({len(template_list)})[/bold green]",
                title_align="left",
                border_style="green",
                width=None
            )
        )
        
    CONSOLE.print(Group(*category_cards))
    
    # 3. Handle selection
    while True:
        tid = input("\nEnter ID to apply (C to cancel): ").upper().strip()
        if tid == 'C': return "Cancelled."
        try: 
            tid_int = int(tid)
            if tid_int in t_map: break
        except: pass
        CONSOLE.print("[red]Invalid ID.[/red]")
        
    name, amt, cat, desc = t_map[tid_int]
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cur = conn.cursor()
    cur.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
               (amt, cat, f"Recurring payment: {name}", today, 'expense'))
    conn.commit(); conn.close()
    return f"[green]Applied '{name}' (£{amt:,.2f}).[/green]"

def get_scheduled_transactions():
    now = datetime.datetime.now().date()
    ym = now.strftime("%Y-%m")
    templates = get_recurring_templates()
    
    # Get recorded descriptions for current month
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cur = conn.cursor()
    cur.execute(f"SELECT description FROM transactions WHERE date LIKE '{ym}-%' AND type='expense'")
    recorded = [r[0] for r in cur.fetchall()]
    
    # Get one-off major expenses
    cur.execute("SELECT amount, description, date FROM transactions WHERE amount > 50 AND type='expense' AND date >= ? ORDER BY date ASC", (now.strftime('%Y-%m-%d'),))
    major = cur.fetchall()
    conn.close()
    
    scheduled = []
    for tid, name, amt, cat, desc, day in templates:
        try: d = datetime.date(now.year, now.month, day)
        except: d = datetime.date(now.year, now.month, 28) # Fallback
        
        desc_check = f"Recurring payment: {name}"
        is_rec = desc_check in recorded
        
        scheduled.append({'date': d.strftime("%Y-%m-%d"), 'amount': amt, 'desc': name, 'type': 'recurring', 'done': is_rec})

    for amt, desc, d_str in major:
        scheduled.append({'date': d_str, 'amount': amt, 'desc': desc, 'type': 'one-off', 'done': True})
        
    return scheduled

def upcoming_calendar():
    now = datetime.datetime.now().date()
    start = now - datetime.timedelta(days=now.weekday())
    events = get_scheduled_transactions()
    
    table = Table(title=f"Week of {start.strftime('%d %b')}", show_header=True, padding=1)
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for d in days: table.add_column(d, justify="center")
    
    row_cells = []
    for i in range(7):
        curr = start + datetime.timedelta(days=i)
        d_str = curr.strftime("%Y-%m-%d")
        
        cell = Text(curr.strftime("%d"), style="bold white")
        if curr == now: cell.style = "bold yellow on blue"
        elif curr < now: cell.style = "dim"
        
        for e in events:
            if e['date'] == d_str:
                amt = e['amount']
                if e['type'] == 'recurring':
                    icon = "✓" if e['done'] else "✗"
                    style = "green" if e['done'] else "red"
                    cell.append(Text.from_markup(f"\n[{style}]{icon}£{amt:.0f}[/{style}]"))
                else:
                    cell.append(Text.from_markup(f"\n[red]!£{amt:.0f}[/red]"))
        row_cells.append(cell)
        
    table.add_row(*row_cells)
    
    # FIX: Use Text.from_markup() here to correctly render the Rich tags in the legend.
    legend_text = Text.from_markup("\nLegend: [red]✗[/red] Due | [green]✓[/green] Paid | [red]![/red] Large Exp")
    show_temporary_view("Calendar", Group(table, legend_text))

def check_and_apply_recurring_payments():
    # Simple check on startup
    now = datetime.datetime.now()
    today_day = now.day
    ym = now.strftime("%Y-%m")
    today_str = now.strftime("%Y-%m-%d")
    
    conn_s = sqlite3.connect(DATABASE_SETTINGS)
    cur_s = conn_s.cursor()
    
    # Get last check
    try: 
        cur_s.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
        last = cur_s.execute("SELECT value FROM meta WHERE key='last_check'").fetchone()
    except: last = None
    
    # If checked today, skip
    if last and last[0] == today_str: 
        conn_s.close(); return None
    
    # Mark checked
    cur_s.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('last_check', ?)", (today_str,))
    conn_s.commit()
    
    templates = get_recurring_templates()
    conn_s.close()
    
    conn_e = sqlite3.connect(DATABASE_EXPENSES)
    cur_e = conn_e.cursor()
    
    applied = []
    for tid, name, amt, cat, desc, day in templates:
        if day == today_day:
            check_desc = f"Recurring payment: {name}"
            # Check if paid this month
            count = cur_e.execute(f"SELECT COUNT(*) FROM transactions WHERE description=? AND date LIKE '{ym}-%'", (check_desc,)).fetchone()[0]
            if count == 0:
                cur_e.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                             (amt, cat, check_desc, today_str, 'expense'))
                applied.append(name)
    
    conn_e.commit(); conn_e.close()
    
    if applied: return f"[green]Auto-paid: {', '.join(applied)}[/green]"
    return None

# --- Category Management ---

def set_savings_goal():
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold yellow]Set Savings Goal[/bold yellow]"))
    while True:
        try:
            target = float(input("Enter Goal Target (£): "))
            current = float(input("Enter Current Saved Amount (£): "))
            if target <= 0 or current < 0:
                CONSOLE.print("[red]Target must be positive, and current saved must be non-negative.[/red]")
                continue
            break
        except ValueError:
            CONSOLE.print("[red]Invalid number.[/red]")
            
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('goal_target', str(target)))
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('current_saved', str(current)))
    conn.commit()
    conn.close()
    return f"[green]Savings goal set to £{target:,.2f} with £{current:,.2f} saved.[/green]"

def add_to_savings():
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold green]Add to Savings[/bold green]"))
    goal_target, current_saved = get_savings_goal()
    if goal_target == 0: return "[red]Set a savings goal first (Option 8).[/red]"
    
    CONSOLE.print(f"[cyan]Current Saved: £{current_saved:,.2f} / Goal: £{goal_target:,.2f}[/cyan]")
    
    while True:
        try:
            amount = float(input("Enter amount to add (£): "))
            if amount <= 0:
                CONSOLE.print("[red]Amount must be positive.[/red]")
                continue
            break
        except ValueError:
            CONSOLE.print("[red]Invalid number.[/red]")

    new_saved = current_saved + amount
    
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('current_saved', str(new_saved)))
    conn.commit()
    conn.close()
    
    # Also record as an expense (transfer out)
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cur_exp = conn_exp.cursor()
    cur_exp.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                   (amount, 'Savings Transfer', 'Transfer to Savings Goal', today, 'expense'))
    conn_exp.commit()
    conn_exp.close()
    
    return f"[green]Added £{amount:,.2f}. New saved total: £{new_saved:,.2f}[/green]"

def add_category_to_db(name):
    conn = sqlite3.connect(DATABASE_SETTINGS)
    try: 
        conn.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit(); msg = f"[bold green]Added category: {name}[/bold green]"
    except sqlite3.IntegrityError: msg = f"[yellow]Category {name} already exists.[/yellow]"
    except Exception as e: msg = f"[bold red]Error adding category: {e}[/bold red]"
    conn.close()
    return msg

def delete_category():
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold red]Delete Category[/bold red]", border_style="red"))
    
    categories_with_ids = get_categories_with_ids()
    
    # Display deletable categories (not protected)
    deletable_cats_with_ids = [(i, name) for i, name in categories_with_ids if name not in PROTECTED_CATEGORIES]
    id_map = {str(i): name for i, name in categories_with_ids} # Map ID to Name globally
    
    if not deletable_cats_with_ids:
        return "[yellow]No custom categories available for deletion.[/yellow]"
        
    cat_list_table = Table(title="Custom Categories (Deletable)", show_header=True, header_style="bold cyan")
    cat_list_table.add_column("ID", style="yellow", width=4)
    cat_list_table.add_column("Name", style="cyan")
    
    for cat_id, name in deletable_cats_with_ids:
        cat_list_table.add_row(str(cat_id), name)
        
    CONSOLE.print(cat_list_table)
    
    CONSOLE.print(f"\n[dim]The following are protected and cannot be deleted: {', '.join(PROTECTED_CATEGORIES)}[/dim]")

    while True:
        id_to_delete = input("\nEnter ID to delete (C to cancel): ").strip()
        if id_to_delete.upper() == 'C': return "Deletion cancelled."
        
        cat_to_delete = id_map.get(id_to_delete)
        
        if cat_to_delete:
            if cat_to_delete in PROTECTED_CATEGORIES:
                CONSOLE.print(f"[bold red]Category '{cat_to_delete}' is protected and cannot be deleted.[/bold red]")
                continue
            break
        
        CONSOLE.print("[bold red]Invalid ID.[/bold red]")


    if input(f"Are you sure you want to delete '{cat_to_delete}'? All transactions will be moved to 'Uncategorized'. (y/n): ").lower() != 'y':
        return "Deletion cancelled."

    # 1. Reassign transactions to 'Uncategorized'
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cur_exp = conn_exp.cursor()
    cur_exp.execute("UPDATE transactions SET category = 'Uncategorized' WHERE category = ?", (cat_to_delete,))
    affected_rows = cur_exp.rowcount
    conn_exp.commit()
    conn_exp.close()

    # 2. Delete category from settings database
    conn_set = sqlite3.connect(DATABASE_SETTINGS)
    cur_set = conn_set.cursor()
    cur_set.execute("DELETE FROM categories WHERE name = ?", (cat_to_delete,))
    conn_set.commit()
    conn_set.close()

    return f"[bold green]Category '{cat_to_delete}' deleted. {affected_rows} transaction(s) reassigned to 'Uncategorized'.[/bold green]"


def manage_categories_full():
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel("[bold yellow]Manage Categories[/bold yellow]", border_style="yellow"))
    
    categories_with_ids = get_categories_with_ids()
    
    cat_list_table = Table(title="Current Categories", show_header=True, header_style="bold cyan")
    cat_list_table.add_column("ID", style="yellow", width=4)
    cat_list_table.add_column("Name", style="cyan")
    
    for cat_id, name in categories_with_ids:
        cat_list_table.add_row(str(cat_id), name)
        
    CONSOLE.print(cat_list_table)
    
    CONSOLE.print("\n[1] Add New | [2] Delete | [C] Cancel")
    ch = input("Choice: ").upper().strip()
    
    if ch == '1': 
        name = input("Enter new category name: ").strip()
        if name: return add_category_to_db(name)
        else: return "[red]Category name cannot be empty.[/red]"
    elif ch == '2':
        return delete_category()
    
    return "Category management cancelled."


def main():
    initialize_db()
    db_check_and_migrate()
    msg = check_and_apply_recurring_payments() or "Welcome!"
    
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        choice = display_dashboard(message=msg)
        msg = ""
        
        if choice == '1': msg = add_transaction()
        elif choice == '2': msg = view_transactions_paginated() # Calls the new card view
        elif choice == '3': msg = filter_by_category() # Calls the new card view for filter
        elif choice == '4': weekly_summary()
        elif choice == '5': monthly_summary()
        elif choice == '6': upcoming_calendar()
        elif choice == '7': msg = delete_transaction()
        elif choice == '8': msg = set_savings_goal()
        elif choice == '9': msg = add_to_savings()
        elif choice == '10': msg = manage_recurring_templates()
        elif choice == '11': msg = apply_recurring_template()
        elif choice == '12': break
        elif choice == '13': msg = manage_categories_full()
        else: msg = "[red]Invalid.[/red]"

if __name__ == "__main__":
    main()
