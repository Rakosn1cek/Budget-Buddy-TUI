import sqlite3
import datetime
import math
import os # Added os import for path manipulation
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn

# --- Configuration and Initialization ---

# Define the absolute, FIXED location where the data files live
# This ensures the script finds the data regardless of the Current Working Directory (CWD).
DATA_DIR = os.path.expanduser('~/Budget-Buddy-TUI')

# Now, define the databases using the fixed path
DATABASE_EXPENSES = os.path.join(DATA_DIR, 'expenses.db')
DATABASE_SETTINGS = os.path.join(DATA_DIR, 'settings.db')

CONSOLE = Console()

# --- Utility Functions for TUI Control ---

def show_temporary_view(title, content):
    """
    Clears the screen, displays a specific piece of content (report/view), 
    waits for user input, and returns. This prevents dashboard stacking.
    """
    # Use os.system('clear') for a more aggressive, reliable clear in TUI/Termux environments
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel(f"[bold magenta]{title}[/bold magenta]", border_style="magenta"))
    CONSOLE.print(content)
    input("\nPress Enter to return to the menu...")
    # NOTE: The next screen clear happens back in the main loop.

def initialize_db():
    """Initializes the expenses, categories, recurring templates, and settings databases."""
    
    # CRITICAL: Ensure the data directory exists before trying to create files in it
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # 1. EXPENSE Database Setup (for all transactions)
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    cursor_exp.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            type TEXT NOT NULL  -- 'income' or 'expense'
        )
    """)
    conn_exp.commit()
    conn_exp.close()

    # 2. SETTINGS Database Setup (for saving goal and recurring templates)
    conn_set = sqlite3.connect(DATABASE_SETTINGS)
    cursor_set = conn_set.cursor()

    # Table for Savings Goal
    cursor_set.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Table for Recurring Templates (Updated with 'due_day')
    cursor_set.execute("""
        CREATE TABLE IF NOT EXISTS recurring_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            due_day INTEGER -- New column for the day of the month (1-31)
        )
    """)
    
    # Table for User Defined Categories
    cursor_set.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            name TEXT PRIMARY KEY
        )
    """)
    
    # Ensure a few default categories exist if the table is empty
    default_categories = ["Uncategorized", "Food", "Rent", "Salary", "Bills", "Savings Transfer"]
    for cat in default_categories:
        try:
            cursor_set.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (cat,))
        except sqlite3.IntegrityError:
            pass # Already exists

    conn_set.commit()
    conn_set.close()

def db_check_and_migrate():
    """Checks the database integrity for new columns and features."""
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    
    # Migration 1: Check for 'type' column in transactions
    try:
        cursor_exp.execute("SELECT type FROM transactions LIMIT 1")
    except sqlite3.OperationalError:
        CONSOLE.print("[yellow]Database migration needed: Adding 'type' column.[/yellow]")
        cursor_exp.execute("ALTER TABLE transactions ADD COLUMN type TEXT DEFAULT 'expense'")
        cursor_exp.execute("UPDATE transactions SET type = 'expense' WHERE type IS NULL")
        CONSOLE.print("[green]Migration complete: 'type' column added and defaulted.[/green]")
        conn_exp.commit()

    conn_exp.close()

    # Migration 2: Check for 'due_day' column in recurring_templates
    conn_set = sqlite3.connect(DATABASE_SETTINGS)
    cursor_set = conn_set.cursor()
    
    try:
        # We need a different check because we use the 'OR REPLACE' template above
        cursor_set.execute("SELECT due_day FROM recurring_templates LIMIT 1")
    except sqlite3.OperationalError:
        CONSOLE.print("[yellow]Settings migration needed: Adding 'due_day' column to recurring templates.[/yellow]")
        cursor_set.execute("ALTER TABLE recurring_templates ADD COLUMN due_day INTEGER DEFAULT 1")
        CONSOLE.print("[green]Migration complete: 'due_day' column added and defaulted to day 1.[/green]")
        conn_set.commit()
        
    conn_set.close()

# --- Core Data Fetching Functions ---

def get_financial_summary():
    """Calculates total income, expenses, and net balance."""
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    
    # Calculate Total Income (type='income')
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='income'")
    total_income = cursor.fetchone()[0] or 0.0

    # Calculate Total Expenses (type='expense')
    cursor.execute("SELECT SUM(amount) FROM transactions WHERE type='expense'")
    total_expenses_raw = cursor.fetchone()[0] or 0.0
    
    # Display expenses as negative for clarity
    total_expenses = total_expenses_raw * -1 
    
    net_balance = total_income + total_expenses
    
    conn.close()
    return total_income, total_expenses, net_balance

def get_savings_goal():
    """Retrieves the current savings goal and saved amount."""
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    
    goal_target = cursor.execute("SELECT value FROM settings WHERE key='goal_target'").fetchone()
    current_saved = cursor.execute("SELECT value FROM settings WHERE key='current_saved'").fetchone()
    
    conn.close()
    
    return (float(goal_target[0]) if goal_target else 0.0,
            float(current_saved[0]) if current_saved else 0.0)

def get_last_n_transactions(n=10):
    """Fetches the last N transactions for dashboard display."""
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    # Fetch N most recent transactions (ordered by date/id descending)
    cursor.execute("SELECT id, amount, category, description, date, type FROM transactions ORDER BY date DESC, id DESC LIMIT ?", (n,))
    transactions = cursor.fetchall()
    conn.close()
    return transactions

def get_categories():
    """Fetches all user-defined categories."""
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM categories ORDER BY name ASC")
    categories = [row[0] for row in cursor.fetchall()]
    conn.close()
    return categories

def display_dashboard(message=""):
    """Renders the complete Budget Buddy TUI dashboard."""
    
    # 1. Clear the screen immediately before drawing the dashboard
    CONSOLE.clear()
    
    # 2. Get current time and format
    now = datetime.datetime.now()
    header_date = now.strftime("%A, %d %b %Y | %H:%M")
    
    # 3. Create Header Panel
    header_content = Text(f"BUDGET BUDDY TUI | {header_date}", style="bold white on purple")
    # Using Panel to draw a border around the header content
    CONSOLE.print(Panel(header_content, title_align="left", border_style="purple"))

    # 4. Get Financial Data
    total_income, total_expenses, net_balance = get_financial_summary()
    recent_transactions = get_last_n_transactions(10)
    
    # 5. Financial Overview Panel Content
    balance_style = "bold green" if net_balance >= 0 else "bold red"
    
    overview_text = Text()
    overview_text.append("Total Income:  ", style="green")
    overview_text.append(f"+£{total_income:,.2f}\n", style="bold green")
    overview_text.append("Total Expenses: ", style="red")
    overview_text.append(f"£{total_expenses:,.2f}\n", style="bold red")
    overview_text.append("NET BALANCE:    ", style="cyan")
    overview_text.append(f"£{net_balance:,.2f}", style=balance_style)
    
    overview_panel = Panel(overview_text, title="FINANCIAL OVERVIEW (All Time)", border_style="cyan", width=87)

    # 6. Savings Goal Panel Content
    goal_target, current_saved = get_savings_goal()
    
    savings_panel_content = None 
    
    if goal_target > 0:
        progress_val = (current_saved / goal_target) * 100 if goal_target > 0 else 0
        progress_val = min(progress_val, 100) # Cap at 100%
        
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

    # 7. Menu Panel Content
    menu_table = Table.grid(padding=(0, 1))
    menu_table.add_column()
    menu_table.add_column()

    # Menu options (Text only, no icons)
    menu_options = [
        ("1. Add Transaction", "bold green"),
        ("2. View Recent Expenses", "bold cyan"),
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
        # Find the first space to split the number/prefix from the description
        parts = text.split(". ", 1)
        number_prefix = parts[0] + "." # Re-add the dot
        description = parts[1]
        menu_table.add_row(f"[bold white]{number_prefix}[/bold white]", Text(description, style=style))

    menu_panel = Panel(menu_table, title="MENU", border_style="magenta", width=87)
    
    # 8. Recent Transactions Panel Content
    recent_tx_table = Table(show_header=True, header_style="bold green", show_lines=False, padding=(0, 1))
    recent_tx_table.add_column("ID", style="dim", min_width=3, width=5)
    recent_tx_table.add_column("Date (MM-DD)", width=8)
    recent_tx_table.add_column("Category", width=10)
    recent_tx_table.add_column("Amount", justify="right", width=12)

    if not recent_transactions:
        # Use a single row to display the message across all columns
        recent_tx_table.add_row(
            Text("", style="dim"),
            Text("[yellow]No recent transactions recorded.[/yellow]", style="yellow"),
            Text("", style="cyan"),
            Text("", justify="right")
        )
    else:
        for tid, amount, category, _, date, t_type in recent_transactions:
            amount_display = f"£{amount:,.0f}"
            if t_type == 'income':
                amount_style = "bold green"
                amount_display = f"+{amount_display}"
            else:
                amount_style = "bold red"
                amount_display = f"-{amount_display}"
                
            recent_tx_table.add_row(
                str(tid),
                date[5:], # Show MM-DD only for brevity
                category[:10],
                Text(amount_display, style=amount_style)
            )

    recent_tx_panel = Panel(recent_tx_table, title="LAST 10 TRANSACTIONS", border_style="green", width=87)
    
    # 9. Assemble Layout - Stacking all panels vertically
    CONSOLE.print(overview_panel)
    CONSOLE.print(savings_panel)
    CONSOLE.print(menu_panel)
    CONSOLE.print(recent_tx_panel) 

    # 10. Print Message and Prompt
    if message:
        # Using Text.from_markup() to correctly parse the color tags in the message string
        message_content = Text.from_markup(message)
        CONSOLE.print(Panel(message_content, title="NOTIFICATION", border_style="yellow", width=87))

    return input("\nSelect an option (1-13): ")

# --- Transaction Management Functions ---

def validate_date(date_str):
    """
    Validates if a string is a date in DD-MM-YYYY format (UK standard).
    Returns the date object if valid, or None if invalid.
    """
    if not date_str:
        # If input is empty, default to today's date
        return datetime.datetime.now().date() 
    try:
        # Attempt to parse as DD-MM-YYYY
        dt_obj = datetime.datetime.strptime(date_str, "%d-%m-%Y")
        return dt_obj.date()
    except ValueError:
        return None

def add_transaction():
    """Allows user to add a new income or expense transaction with date selection."""
    # We rely on main loop clear before display_dashboard is called
    CONSOLE.print(Panel("[bold magenta]Add New Transaction[/bold magenta]", border_style="magenta"))
    
    # 1. Get Type
    while True:
        t_type = input("Type [I]ncome or [E]xpense: ").lower()
        if t_type in ('i', 'income'):
            transaction_type = 'income'
            break
        elif t_type in ('e', 'expense'):
            transaction_type = 'expense'
            break
        CONSOLE.print("[bold red]Invalid type. Enter 'I' or 'E'.[/bold red]")

    # 2. Get Amount
    while True:
        try:
            amount_input = float(input(f"Enter amount (£): "))
            if amount_input <= 0:
                CONSOLE.print("[bold red]Amount must be positive.[/bold red]")
                continue
            
            amount = amount_input
            break
        except ValueError:
            CONSOLE.print("[bold red]Invalid number format. Please enter a numerical value.[/bold red]")

    # 3. Get Category
    available_categories = get_categories()
    categories_list = ", ".join(available_categories)
    CONSOLE.print(f"\n[cyan]Available Categories:[/cyan] {categories_list}")

    while True:
        category = input("Enter Category (or select from list above): ").strip()
        if not category:
            category = "Uncategorized"
        
        # Simple validation: if user enters a new category, add it automatically
        if category not in available_categories:
            if input(f"Category '{category}' not found. Add it? (y/n): ").lower() == 'y':
                add_category_to_db(category)
                break
            else:
                CONSOLE.print("[bold red]Please select an existing category or add a new one.[/bold red]")
                continue
        break


    # 4. Get Description
    description = input("Enter short description (optional): ").strip()

    # 5. Get Date (Updated Feature for DD-MM-YYYY)
    default_date = datetime.datetime.now().strftime("%d-%m-%Y")
    while True:
        date_input = input(f"Enter Date (DD-MM-YYYY, default: {default_date}): ").strip()
        
        # Pass the input to the validator
        dt_obj_or_none = validate_date(date_input) 

        if dt_obj_or_none is not None:
            # Convert the valid date object back to the DB standard format (YYYY-MM-DD)
            date_str = dt_obj_or_none.strftime("%Y-%m-%d") 
            break
        
        CONSOLE.print("[bold red]Invalid date format. Please use DD-MM-YYYY.[/bold red]")


    # 6. Save to DB
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                   (amount, category, description, date_str, transaction_type))
    conn.commit()
    conn.close()

    # Display confirmation message with the user's preferred date format for feedback
    display_date = dt_obj_or_none.strftime("%d-%m-%Y")
    return f"[bold green]Successfully recorded {transaction_type.upper()} of £{amount:,.2f} under {category} on {display_date}.[/bold green]"

def view_transactions(filter_query=None, title="Recent Expenses"):
    """Fetches and formats a list of transactions for display in a temporary view."""
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    
    sql_query = "SELECT id, amount, category, description, date, type FROM transactions ORDER BY date DESC, id DESC LIMIT 50"
    params = ()
    
    if filter_query:
        sql_query = f"SELECT id, amount, category, description, date, type FROM transactions WHERE category LIKE ? ORDER BY date DESC, id DESC"
        params = ('%' + filter_query + '%',)
        title = f"Filtered Transactions: '{filter_query}'"

    cursor.execute(sql_query, params)
    transactions = cursor.fetchall()
    conn.close()

    if not transactions:
        return Group(Text("[yellow]No transactions found matching the criteria.[/yellow]")), title

    table = Table(title="Transaction History (Latest 50)", title_style="bold yellow", show_header=True, header_style="bold magenta", padding=(0,1))
    
    # Column definitions with tight widths for mobile
    table.add_column("ID", style="dim", min_width=3, width=5) 
    table.add_column("Date (MM-DD)", style="bold white", width=8) 
    table.add_column("Category", style="cyan", width=10)
    table.add_column("Description", style="white", width=12) 
    table.add_column("Amount", style="bold", justify="right", width=12)
    
    for tid, amount, category, description, date_db, t_type in transactions:
        amount_display = f"£{amount:,.2f}"
        
        # Convert DB date (YYYY-MM-DD) to Display date (MM-DD)
        try:
            display_date = datetime.datetime.strptime(date_db, "%Y-%m-%d").strftime("%m-%d") 
        except ValueError:
            display_date = date_db # Fallback if DB format is corrupted
            
        if t_type == 'income':
            amount_style = "bold green"
            amount_display = f"+{amount_display}"
        else: # expense
            amount_style = "bold red"
            amount_display = f"-{amount_display}"
            
        table.add_row(
            str(tid),
            display_date,
            category[:10], # Truncate category if needed
            description[:12] if description else "---", # Truncate description if needed
            Text(amount_display, style=amount_style)
        )
        
    return table, title

def delete_transaction():
    """Prompts for transaction ID and deletes it."""
    # 1. Get the list of transactions
    table, title = view_transactions(title="Transactions to Delete (Latest 50)")

    # 2. Clear the screen and display the transaction list 
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel(f"[bold red]{title}[/bold red]", border_style="red"))
    CONSOLE.print(table) 

    # 3. Get the ID to delete 
    while True:
        try:
            tid = input("\nEnter ID of transaction to delete (or 'C' to cancel): ").upper().strip()
            if tid == 'C':
                return "Deletion cancelled."
                
            tid_int = int(tid)
            break
        except ValueError:
            CONSOLE.print("[bold red]Invalid ID. Please enter a number or 'C'.[/bold red]")
            
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM transactions WHERE id = ?", (tid_int,))
    
    if cursor.rowcount > 0:
        conn.commit()
        conn.close()
        return f"[bold green]Transaction ID {tid_int} deleted successfully.[/bold green]"
    else:
        conn.close()
        return f"[bold red]Error: No transaction found with ID {tid_int}.[/bold red]"

def filter_by_category():
    """Prompts the user for a category filter and displays results."""
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel("[bold magenta]Filter Transactions by Category[/bold magenta]", border_style="magenta"))
    category = input("Enter the category to filter by (e.g., Food, Bills): ").strip()
    
    if category:
        table, title = view_transactions(filter_query=category)
        show_temporary_view(title, table)
        return f"[bold green]Filter applied for category: {category}[/bold green]"
    else:
        return "[yellow]Filter cancelled. Returning to menu.[/yellow]"

# --- Summary & Reporting Functions ---

def get_transaction_data(start_date=None, end_date=None):
    """Fetches transactions within a date range and groups them by category and type."""
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    
    sql_query = "SELECT amount, category, type FROM transactions"
    params = []
    
    if start_date and end_date:
        sql_query += " WHERE date BETWEEN ? AND ?"
        params = [start_date, end_date]

    cursor.execute(sql_query, params)
    transactions = cursor.fetchall()
    conn.close()
    
    category_summary = {} # {category: {'expense': amount, 'income': amount}}
    
    for amount, category, t_type in transactions:
        category = category.strip()
        if category not in category_summary:
            category_summary[category] = {'expense': 0.0, 'income': 0.0}
            
        if t_type == 'income':
            category_summary[category]['income'] += amount
        else: # expense
            category_summary[category]['expense'] += amount
            
    return category_summary

def monthly_summary():
    """Generates a detailed summary of income and expenses per category for the current month."""
    now = datetime.datetime.now()
    start_date = now.strftime("%Y-%m-01")
    end_date = now.strftime("%Y-%m-%d") # Current day is the end date
    
    category_data = get_transaction_data(start_date, end_date)
    
    title = f"Monthly Detailed Summary: {now.strftime('%B %Y')}"
    
    if not category_data:
        show_temporary_view(title, Text("[yellow]No transactions recorded this month.[/yellow]"))
        return

    table = Table(title="Category Breakdown", title_style="bold yellow", show_header=True, header_style="bold cyan", padding=1)
    table.add_column("Category", style="bold white", width=20)
    table.add_column("Total Income", style="green", justify="right")
    table.add_column("Total Expenses", style="red", justify="right")
    table.add_column("Net", style="yellow", justify="right")
    
    total_monthly_income = 0.0
    total_monthly_expense = 0.0

    for category, amounts in category_data.items():
        income = amounts['income']
        expense = amounts['expense']
        net = income - expense
        
        total_monthly_income += income
        total_monthly_expense += expense

        net_style = "bold green" if net >= 0 else "bold red"
        
        table.add_row(
            category,
            f"+£{income:,.2f}",
            f"-£{expense:,.2f}",
            Text(f"£{net:,.2f}", style=net_style)
        )
    
    # Footer Summary (FIXED: Used Text.from_markup to correctly parse color tags)
    final_net = total_monthly_income - total_monthly_expense
    final_net_style = "bold green" if final_net >= 0 else "bold red"
    
    footer = Group(
        table,
        Text("\n" + "="*50),
        Text.from_markup(f"[green]TOTAL MONTHLY INCOME:  +£{total_monthly_income:,.2f}[/green]"),
        Text.from_markup(f"[red]TOTAL MONTHLY EXPENSE: -£{total_monthly_expense:,.2f}[/red]"),
        Text(f"MONTHLY NET BALANCE:   £{final_net:,.2f}", style=final_net_style),
        Text("="*50)
    )

    show_temporary_view(title, footer)

def weekly_summary():
    """Generates a summary of income and expenses per category for the current week (Mon-Sun)."""
    now = datetime.datetime.now()
    
    # Calculate start (Monday) and end (Sunday) of the current week
    start_date = now - datetime.timedelta(days=now.weekday())
    end_date = start_date + datetime.timedelta(days=6)
    
    start_date_str = start_date.strftime("%Y-%m-%d")
    end_date_str = end_date.strftime("%Y-%m-%d")
    
    category_data = get_transaction_data(start_date_str, end_date_str)
    
    title = f"Weekly Summary: {start_date.strftime('%d %b')} - {end_date.strftime('%d %b')}"
    
    if not category_data:
        show_temporary_view(title, Text("[yellow]No transactions recorded this week.[/yellow]"))
        return

    # Aggregate data for display
    table = Table(title="Weekly Category Summary", title_style="bold magenta", show_header=True, header_style="bold magenta", padding=1)
    table.add_column("Category", style="bold white", width=20)
    table.add_column("Total Expenses", style="red", justify="right")
    table.add_column("Total Income", style="green", justify="right")
    
    total_weekly_expense = 0.0
    total_weekly_income = 0.0

    for category, amounts in category_data.items():
        income = amounts['income']
        expense = amounts['expense']
        
        total_weekly_income += income
        total_weekly_expense += expense
        
        table.add_row(
            category,
            f"-£{expense:,.2f}",
            f"+£{income:,.2f}"
        )
    
    # Footer Summary (FIXED: Used Text.from_markup to correctly parse color tags)
    final_net = total_weekly_income - total_weekly_expense
    final_net_style = "bold green" if final_net >= 0 else "bold red"
    
    footer = Group(
        table,
        Text("\n" + "-"*50),
        Text.from_markup(f"[green]TOTAL WEEKLY INCOME:  +£{total_weekly_income:,.2f}[/green]"),
        Text.from_markup(f"[red]TOTAL WEEKLY EXPENSE: -£{total_weekly_expense:,.2f}[/red]"),
        Text(f"WEEKLY NET BALANCE:   £{final_net:,.2f}", style=final_net_style),
        Text("-"*50)
    )
    
    show_temporary_view(title, footer)

def get_recurring_templates():
    """Fetches all recurring templates with the new due_day."""
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    # Ensure all columns are explicitly selected, including the new 'due_day'
    cursor.execute("SELECT id, name, amount, category, description, due_day FROM recurring_templates")
    templates = cursor.fetchall()
    conn.close()
    return templates

def get_scheduled_transactions():
    """Returns a list of tuples containing (amount, description, date_str) for all upcoming expenses."""
    now = datetime.datetime.now().date()
    current_year_month = now.strftime("%Y-%m")
    
    # 1. Fetch all recurring templates
    templates = get_recurring_templates()
    
    # 2. Get transactions already recorded this month for comparison
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    # Only check for transactions recorded in the current month
    cursor_exp.execute(f"SELECT description FROM transactions WHERE date LIKE '{current_year_month}-%' AND type='expense'")
    recorded_descriptions = [row[0] for row in cursor_exp.fetchall()]
    conn_exp.close()

    scheduled = []
    for tid, name, amount, category, desc, due_day in templates:
        # Determine the date for this month
        try:
            # Handle cases where the due_day might exceed the days in the current month (e.g., Feb 30)
            scheduled_date = datetime.date(now.year, now.month, due_day)
        except ValueError:
            # If the day doesn't exist, schedule for the last day of the month
            import calendar
            last_day = calendar.monthrange(now.year, now.month)[1]
            scheduled_date = datetime.date(now.year, now.month, last_day)

        
        date_str = scheduled_date.strftime("%Y-%m-%d")
        description = f"Recurring payment: {name}"
        
        is_recorded = description in recorded_descriptions

        scheduled.append({
            'amount': amount,
            'description': description,
            'date_str': date_str,
            'is_recurring': True,
            'is_recorded': is_recorded
        })
        
    # 3. Fetch large one-off expenses (> 50) as before
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    # Filter for large, unrecorded one-off expenses in the near future
    cursor_exp.execute("SELECT amount, description, date FROM transactions WHERE amount > 50 AND type='expense' AND date >= ? ORDER BY date ASC", (now.strftime('%Y-%m-%d'),))
    major_expenses = cursor_exp.fetchall()
    conn_exp.close()

    for amount, desc, date_str in major_expenses:
        scheduled.append({
            'amount': amount,
            'description': desc,
            'date_str': date_str,
            'is_recurring': False,
            'is_recorded': True # Already recorded, just displaying it
        })
        
    return scheduled

def upcoming_calendar():
    """
    Displays a calendar view for the current week showing dates and notes 
    for all scheduled recurring payments and major expenses.
    """
    now = datetime.datetime.now().date()
    # Find the start of the current week (Monday)
    start_of_week = now - datetime.timedelta(days=now.weekday())
    end_of_week = start_of_week + datetime.timedelta(days=6)
    
    title = f"Upcoming Calendar View: {start_of_week.strftime('%d %b')} - {end_of_week.strftime('%d %b')}"
    
    # Get all scheduled and major expenses
    scheduled_events = get_scheduled_transactions()

    # The calendar table
    calendar_table = Table(title=f"Week of {start_of_week.strftime('%d %b')}", title_style="bold white", show_header=True, header_style="bold yellow", padding=1)
    
    days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for day in days_of_week:
        calendar_table.add_column(day, justify="center")

    all_rows = []
    current_row = []
    
    # Iterate through only 1 week (1 row)
    for day_offset in range(7):
        current_date = start_of_week + datetime.timedelta(days=day_offset)
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Start the cell content with the date number
        cell_text = Text(current_date.strftime("%d"), style="bold white")
        
        if current_date < now:
            cell_text.style = "dim"
        elif current_date == now:
            cell_text.style = "bold yellow on blue"
            
        expense_notes = []
        for event in scheduled_events:
            if event['date_str'] == date_str:
                amount = event['amount']
                desc = event['description']
                
                if event['is_recurring']:
                    if event['is_recorded']:
                        # Auto-applied recurring payment
                        style = "bold green"
                        note_text = f"✓ R-£{amount:,.0f}"
                    else:
                        # Scheduled recurring payment (Reminder)
                        style = "bold red"
                        note_text = f"✗ R-£{amount:,.0f}"
                else:
                    # Large one-off expense
                    style = "bold red"
                    note_text = f"O-£{amount:,.0f}"
                    
                # Truncate description for display in the calendar cell
                desc_part = desc.split(':')[-1].strip()
                note_desc = f" ({desc_part[:8]}...)" if len(desc_part) > 8 else f" ({desc_part})"
                
                # FIX: Use Text.from_markup() to correctly parse the rich markup string 
                # before appending it to the main cell_text object.
                note_line = Text.from_markup(f"\n[{style}]{note_text}[/{style}]{note_desc}")
                expense_notes.append(note_line)

        # Append all expense notes (which are now Text objects) to the main cell Text object
        for note in expense_notes:
            cell_text.append(note)
        
        current_row.append(cell_text)
    
    all_rows.append(current_row)

    # Add rows to the table
    for row in all_rows:
        calendar_table.add_row(*row)
    
    legend = Text.from_markup("\n[bold]Legend:[/bold] [bold red]✗ R[/bold red]=Recurring Due | [bold green]✓ R[/bold green]=Recurring Paid | [bold red]O[/bold red]=One-Off > £50")
    content = Group(
        calendar_table,
        legend
    )
        
    show_temporary_view(title, content)

# --- Savings Goal Functions ---

def set_savings_goal():
    """Sets a target amount for the savings goal."""
    # We rely on main loop clear before display_dashboard is called
    CONSOLE.print(Panel("[bold yellow]Set Savings Goal Target[/bold yellow]", border_style="yellow"))
    
    while True:
        try:
            target = float(input("Enter new savings goal target (£): "))
            if target <= 0:
                CONSOLE.print("[bold red]Target must be a positive number.[/bold red]")
                continue
            break
        except ValueError:
            CONSOLE.print("[bold red]Invalid number format.[/bold red]")

    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    
    # Set the goal target
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('goal_target', str(target)))
    
    # Initialize current saved amount if it doesn't exist
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", ('current_saved', '0.0'))
    
    conn.commit()
    conn.close()
    
    return f"[bold green]Savings goal set to £{target:,.2f}.[/bold green]"

def add_to_savings():
    """Transfers money from Net Balance to the Savings Goal."""
    goal_target, current_saved = get_savings_goal()

    if goal_target <= 0:
        return "[bold red]Error: Please set a savings goal first (Option 8).[/bold red]"

    _, _, net_balance = get_financial_summary()
    
    # We rely on main loop clear before display_dashboard is called
    CONSOLE.print(Panel("[bold green]Add to Savings Goal[/bold green]", border_style="green"))
    CONSOLE.print(f"Current Net Balance: [bold cyan]£{net_balance:,.2f}[/bold cyan]")
    CONSOLE.print(f"Goal Progress: [bold yellow]£{current_saved:,.2f}[/bold yellow] / [bold yellow]£{goal_target:,.2f}[/bold yellow]")
    
    while True:
        try:
            transfer_amount = float(input("Enter amount to transfer to savings (£): "))
            if transfer_amount <= 0:
                CONSOLE.print("[bold red]Amount must be positive.[/bold red]")
                continue
            
            # Check if user has enough balance
            if transfer_amount > net_balance:
                CONSOLE.print("[bold red]Insufficient funds in Net Balance.[/bold red]")
                continue
            
            break
        except ValueError:
            CONSOLE.print("[bold red]Invalid number format.[/bold red]")
            
    # 1. Update Savings Goal
    new_saved = current_saved + transfer_amount
    conn_set = sqlite3.connect(DATABASE_SETTINGS)
    cursor_set = conn_set.cursor()
    cursor_set.execute("UPDATE settings SET value = ? WHERE key = 'current_saved'", (str(new_saved),))
    conn_set.commit()
    conn_set.close()

    # 2. Record as a special 'Transfer' expense transaction
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    cursor_exp.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                       (transfer_amount, 'Savings Transfer', 'Transfer to Savings Goal', date_str, 'expense'))
    conn_exp.commit()
    conn_exp.close()
    
    return f"[bold green]£{transfer_amount:,.2f} transferred and recorded as expense. Saved amount is now £{new_saved:,.2f}.[/bold green]"

# --- Recurring Template Functions ---

def manage_recurring_templates():
    """Allows user to view, add, or delete recurring transaction templates."""
    templates = get_recurring_templates()

    # We rely on main loop clear before display_dashboard is called
    CONSOLE.print(Panel("[bold orange1]Manage Recurring Templates[/bold orange1]", border_style="orange1"))

    if templates:
        table = Table(title="Available Templates", show_header=True, header_style="bold orange1")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Due Day", style="yellow", width=8, justify="center") # New Column
        table.add_column("Name", style="bold white", width=20)
        table.add_column("Amount", style="red", width=10, justify="right")
        table.add_column("Category", style="cyan", width=15)
        
        for tid, name, amount, category, desc, due_day in templates:
            table.add_row(str(tid), str(due_day), name, f"£{amount:,.2f}", category)
        
        CONSOLE.print(table)
    else:
        CONSOLE.print("[yellow]No recurring templates defined yet.[/yellow]")

    # Sub-menu for management
    CONSOLE.print("\n[1] Add New Template(s) | [2] Delete Template | [C] Cancel")
    choice = input("Select an option: ").upper().strip()

    if choice == '1':
        return add_recurring_template() # Now handles the loop internally
    elif choice == '2':
        return delete_recurring_template(templates)
    else:
        return "Template management cancelled."


def add_recurring_template():
    """
    Adds one or more new recurring templates in a continuous loop 
    until the user chooses to stop.
    """
    templates_added = 0
    
    while True:
        # Clear the screen only when entering the template creation loop
        os.system('cls' if os.name == 'nt' else 'clear')
        CONSOLE.print(Panel(f"[bold green]Add New Recurring Template ({templates_added} added)[/bold green]", border_style="green"))
        
        # 1. Get Name (and allow for cancel)
        name_input = input("Enter Template Name (e.g., Rent, Netflix, or 'C' to cancel): ").strip()
        if name_input.upper() == 'C':
            break
        
        name = name_input
        
        # 2. Get Amount
        while True:
            try:
                amount = float(input("Enter monthly amount (£): "))
                if amount <= 0:
                    CONSOLE.print("[bold red]Amount must be positive.[/bold red]")
                    continue
                break
            except ValueError:
                CONSOLE.print("[bold red]Invalid number format.[/bold red]")

        # 3. Get Due Day of Month
        while True:
            try:
                due_day = int(input("Enter Due Day of Month (1-31, e.g., 5 for the 5th): "))
                if 1 <= due_day <= 31:
                    break
                CONSOLE.print("[bold red]Due day must be between 1 and 31.[/bold red]")
            except ValueError:
                CONSOLE.print("[bold red]Invalid number format for due day.[/bold red]")

        # 4. Get Category
        category = input("Enter Category: ").strip()
        if not category:
            category = "Uncategorized"
            
        # 5. Get Description
        description = input("Enter description (optional): ").strip()

        # 6. Save to DB
        conn = sqlite3.connect(DATABASE_SETTINGS)
        cursor = conn.cursor()
        
        try:
            cursor.execute("INSERT INTO recurring_templates (name, amount, category, description, due_day) VALUES (?, ?, ?, ?, ?)",
                           (name, amount, category, description, due_day))
            conn.commit()
            templates_added += 1
            CONSOLE.print(f"[bold green]Template '{name}' (Due Day: {due_day}) added successfully.[/bold green]")
        except sqlite3.IntegrityError:
            CONSOLE.print(f"[bold red]Error: Template name '{name}' already exists. Skipping.[/bold red]")
        finally:
            conn.close()

        # 7. Ask for continuation
        if input("\nDo you want to add another template? (y/n): ").lower() != 'y':
            break
    
    if templates_added > 0:
        return f"[bold green]Finished adding templates. Total added: {templates_added}.[/bold green]"
    return "Template addition cancelled."

def delete_recurring_template(templates):
    """Deletes a recurring template by ID."""
    # We clear again if we come from manage_recurring_templates
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel("[bold red]Delete Recurring Template[/bold red]", border_style="red"))
    
    if not templates:
        return "[yellow]No templates to delete.[/yellow]"
        
    while True:
        try:
            tid = input("\nEnter ID of template to delete (or 'C' to cancel): ").upper().strip()
            if tid == 'C':
                return "Deletion cancelled."
            tid_int = int(tid)
            break
        except ValueError:
            CONSOLE.print("[bold red]Invalid ID. Please enter a number or 'C'.[/bold red]")
            
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM recurring_templates WHERE id = ?", (tid_int,))
    
    if cursor.rowcount > 0:
        conn.commit()
        result_msg = f"\n[bold green]Template ID {tid_int} deleted successfully.[/bold green]"
    else:
        result_msg = f"\n[bold red]Error: No template found with ID {tid_int}.[/bold red]"
    
    conn.close()
    return result_msg

def apply_recurring_template():
    """Applies a recurring template, recording it as an expense transaction."""
    templates = get_recurring_templates()

    if not templates:
        return "[bold red]No recurring templates found. Use option 10 to create one first.[/bold red]"

    # We rely on main loop clear before display_dashboard is called
    CONSOLE.print(Panel("[bold green]Apply Recurring Payment[/bold green]", border_style="green"))
    
    # Display templates for selection
    table = Table(title="Select Template", show_header=True, header_style="bold green")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Due Day", style="yellow", width=8, justify="center")
    table.add_column("Name", style="bold white", width=20)
    table.add_column("Amount", style="red", width=10)
    table.add_column("Category", style="cyan", width=15)
    
    template_map = {}
    for tid, name, amount, category, _, due_day in templates:
        table.add_row(str(tid), str(due_day), name, f"£{amount:,.2f}", category)
        # Store as a dict for easy lookup
        template_map[tid] = {'amount': amount, 'category': category, 'name': name}
    
    CONSOLE.print(table)

    while True:
        try:
            template_id_input = input("\nEnter ID of template to apply (or 'C' to cancel): ").upper().strip()
            if template_id_input == 'C':
                return "Application cancelled."
                
            template_id = int(template_id_input)
            
            if template_id not in template_map:
                CONSOLE.print("[bold red]Invalid Template ID.[/bold red]")
                continue
                
            break
        except ValueError:
            CONSOLE.print("[bold red]Invalid ID. Please enter a number or 'C'.[/bold red]")

    template_data = template_map[template_id]
    amount = template_data['amount']
    category = template_data['category']
    name = template_data['name']
    
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    description = f"Recurring payment: {name}"

    # Record the expense transaction
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    cursor_exp.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                       (amount, category, description, date_str, 'expense'))
    conn_exp.commit()
    conn_exp.close()
    
    return f"[bold green]Successfully applied recurring payment '{name}' (Expense: £{amount:,.2f}) manually.[/bold green]"

# --- Category Management Functions ---

def add_category_to_db(category_name):
    """Helper function to add a category to the database."""
    category_name = category_name.strip()
    if not category_name:
        return "[bold red]Category name cannot be empty.[/bold red]"
    
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (category_name,))
        conn.commit()
        return f"[bold green]Category '{category_name}' added.[/bold green]"
    except sqlite3.IntegrityError:
        return f"[yellow]Category '{category_name}' already exists.[/yellow]"
    finally:
        conn.close()

def manage_categories():
    """Provides a menu to view, add, or delete categories."""
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel("[bold yellow]Manage Budget Categories[/bold yellow]", border_style="yellow"))

    categories = get_categories()
    
    table = Table(title="Current Categories", title_style="bold yellow", show_header=True, header_style="bold cyan")
    table.add_column("Category Name", style="bold white")
    
    for cat in categories:
        table.add_row(cat)
    
    CONSOLE.print(table)
    
    CONSOLE.print("\n[1] Add New Category | [2] Delete Category | [C] Cancel")
    choice = input("Select an option: ").upper().strip()

    if choice == '1':
        return prompt_add_category()
    elif choice == '2':
        return prompt_delete_category(current_categories=categories)
    else:
        return "Category management cancelled."

def prompt_add_category():
    """Prompts user to add a new category."""
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel("[bold green]Add New Category[/bold green]", border_style="green"))
    name = input("Enter new category name: ").strip()
    return add_category_to_db(name)

def prompt_delete_category(current_categories):
    """Prompts user to delete an existing category."""
    os.system('cls' if os.name == 'nt' else 'clear')
    CONSOLE.print(Panel("[bold red]Delete Category[/bold red]", border_style="red"))
    
    if not current_categories:
        return "[yellow]No categories to delete.[/yellow]"
        
    name = input("Enter category name to delete: ").strip()
    
    # Preventing deletion of critical categories
    if name in ["Uncategorized", "Savings Transfer"]:
        return f"[bold red]Error: '{name}' is a system category and cannot be deleted.[/bold red]"
        
    if name not in current_categories:
        return f"[bold red]Error: Category '{name}' not found.[/bold red]"

    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    
    # 1. Check if category is used in transactions
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    cursor_exp.execute("SELECT COUNT(*) FROM transactions WHERE category = ?", (name,))
    usage_count = cursor_exp.fetchone()[0]
    conn_exp.close()

    if usage_count > 0:
        if input(f"Warning: '{name}' is used in {usage_count} transactions. Delete anyway and re-categorize transactions to 'Uncategorized'? (y/n): ").lower() != 'y':
            conn.close()
            return "Deletion cancelled."
            
        # 2. Re-categorize old transactions
        conn_exp = sqlite3.connect(DATABASE_EXPENSES)
        cursor_exp = conn_exp.cursor()
        cursor_exp.execute("UPDATE transactions SET category = 'Uncategorized' WHERE category = ?", (name,))
        conn_exp.commit()
        conn_exp.close()
        
    # 3. Delete the category from the settings database
    cursor.execute("DELETE FROM categories WHERE name = ?", (name,))
    
    if cursor.rowcount > 0:
        conn.commit()
        result_msg = f"[bold green]Category '{name}' deleted and {usage_count} transactions moved to 'Uncategorized'.[/bold green]"
    else:
        result_msg = f"[bold red]Error deleting category '{name}'.[/bold red]"
    
    conn.close()
    return result_msg

# --- Automation Function ---

def check_and_apply_recurring_payments():
    """
    Checks if any recurring payments are due today and have not been recorded 
    in the current month. If so, records them automatically.
    """
    now = datetime.datetime.now()
    today_day = now.day
    current_date_str = now.strftime("%Y-%m-%d")
    current_month_prefix = now.strftime("%Y-%m-")
    
    templates = get_recurring_templates()
    
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    
    applied_templates = []

    for tid, name, amount, category, _, due_day in templates:
        # Check if today is the due day
        if due_day == today_day:
            description = f"Recurring payment: {name}"
            
            # Check if this payment has ALREADY been applied this month
            # We look for any transaction this month with the exact recurring description
            cursor_exp.execute("SELECT COUNT(*) FROM transactions WHERE description = ? AND date LIKE ?", 
                               (description, f'{current_month_prefix}%'))
            
            if cursor_exp.fetchone()[0] == 0:
                # Payment is due AND has not been recorded this month. Apply it.
                cursor_exp.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                                   (amount, category, description, current_date_str, 'expense'))
                applied_templates.append(f"'{name}' (£{amount:,.2f})")
                
    conn_exp.commit()
    conn_exp.close()
    
    if applied_templates:
        return f"[bold green]AUTOMATICALLY APPLIED PAYMENTS:[/bold green] {', '.join(applied_templates)}"
    return None # No automatic payment was made

# --- Main Application Loop ---

def main():
    """The main entry point for the Budget Buddy TUI."""
    initialize_db()
    db_check_and_migrate()
    message = "Welcome to Budget Buddy TUI! Ready for action."
    
    # Run automation check right after initialization
    auto_message = check_and_apply_recurring_payments()
    if auto_message:
        # Prepend the automated message to the welcome message
        message = f"{auto_message}\n{message}"

    while True:
        # CRITICAL FIX: Use os.system('clear') before every dashboard redraw 
        # for maximum compatibility and to eliminate screen ghosting.
        os.system('cls' if os.name == 'nt' else 'clear')
        
        choice = display_dashboard(message)
        message = "" # Reset message after display

        try:
            # We rely on string input for this loop, though some commands expect an int
            if choice.upper() == 'C':
                message = "[yellow]Action cancelled.[/yellow]"
                continue
                
            choice_int = int(choice)
        except ValueError:
            message = "[bold red]Invalid input. Please enter a number between 1 and 13.[/bold red]"
            continue

        # Execute the chosen action
        if choice_int == 1:
            message = add_transaction()
        elif choice_int == 2:
            table, title = view_transactions()
            show_temporary_view(title, table)
        elif choice_int == 3:
            message = filter_by_category() # Handles its own view/pause
        elif choice_int == 4:
            weekly_summary() # Handles its own view/pause
        elif choice_int == 5:
            monthly_summary() # Handles its own view/pause
        elif choice_int == 6:
            upcoming_calendar() # Handles its own view/pause
        elif choice_int == 7:
            message = delete_transaction()
        elif choice_int == 8:
            message = set_savings_goal()
        elif choice_int == 9:
            message = add_to_savings()
        elif choice_int == 10:
            message = manage_recurring_templates()
        elif choice_int == 11:
            message = apply_recurring_template()
        elif choice_int == 12:
            CONSOLE.print(Panel(Text("Thank you for using Budget Buddy. Goodbye!", style="bold magenta"), border_style="magenta"))
            break
        elif choice_int == 13: # New Option for Category Management
            message = manage_categories()
        else:
            message = "[bold red]Invalid option. Please enter a number between 1 and 13.[/bold red]"
        
        # The main loop continues, and the first line of the loop will always run CONSOLE.clear() again.

if __name__ == '__main__':
    main()
