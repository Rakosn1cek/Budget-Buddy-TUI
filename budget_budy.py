import sqlite3
import datetime
import math
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn

# --- Configuration and Initialization ---
DATABASE_EXPENSES = 'expenses.db'
DATABASE_SETTINGS = 'settings.db'
CONSOLE = Console()

# --- Utility Functions for TUI Control ---

def show_temporary_view(title, content):
    """
    Clears the screen, displays a specific piece of content (report/view), 
    waits for user input, and returns. This prevents dashboard stacking.
    """
    CONSOLE.clear()
    CONSOLE.print(Panel(f"[bold magenta]{title}[/bold magenta]", border_style="magenta"))
    CONSOLE.print(content)
    input("\nPress Enter to return to the menu...")
    # NOTE: The next CONSOLE.clear() happens back in the main loop.

def initialize_db():
    """Initializes the expenses, categories, recurring templates, and settings databases."""
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

    # Table for Recurring Templates (New Feature)
    cursor_set.execute("""
        CREATE TABLE IF NOT EXISTS recurring_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT
        )
    """)
    conn_set.commit()
    conn_set.close()

def db_check_and_migrate():
    """Checks the database integrity for new columns and features."""
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()

    # Check for 'type' column (1st migration)
    try:
        cursor.execute("SELECT type FROM transactions LIMIT 1")
    except sqlite3.OperationalError:
        CONSOLE.print("[yellow]Database migration needed: Adding 'type' column.[/yellow]")
        cursor.execute("ALTER TABLE transactions ADD COLUMN type TEXT DEFAULT 'expense'")
        # Assume all existing entries were expenses for safety
        cursor.execute("UPDATE transactions SET type = 'expense' WHERE type IS NULL")
        CONSOLE.print("[green]Migration complete: 'type' column added and defaulted.[/green]")
        conn.commit()

    conn.close()

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

def display_dashboard(message=""):
    """Renders the complete Budget Buddy TUI dashboard."""
    
    # 1. Get current time and format
    now = datetime.datetime.now()
    header_date = now.strftime("%A, %d %b %Y | %H:%M")
    
    # 2. Create Header Panel
    header_content = Text(f"BUDGET BUDDY TUI | {header_date}", style="bold white on purple")
    # Using Panel to draw a border around the header content
    CONSOLE.print(Panel(header_content, title_align="left", border_style="purple"))

    # 3. Get Financial Data
    total_income, total_expenses, net_balance = get_financial_summary()
    recent_transactions = get_last_n_transactions(10)
    
    # 4. Financial Overview Panel Content
    balance_style = "bold green" if net_balance >= 0 else "bold red"
    
    overview_text = Text()
    overview_text.append("Total Income:  ", style="green")
    overview_text.append(f"+£{total_income:,.2f}\n", style="bold green")
    overview_text.append("Total Expenses: ", style="red")
    overview_text.append(f"£{total_expenses:,.2f}\n", style="bold red")
    overview_text.append("NET BALANCE:    ", style="cyan")
    overview_text.append(f"£{net_balance:,.2f}", style=balance_style)
    
    overview_panel = Panel(overview_text, title="FINANCIAL OVERVIEW (All Time)", border_style="cyan", width=87)

    # 5. Savings Goal Panel Content
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

    # 6. Menu Panel Content
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
        ("12. Exit Application", "bold white")
    ]

    for i, (text, style) in enumerate(menu_options):
        # Find the first space to split the number/prefix from the description
        parts = text.split(". ", 1)
        number_prefix = parts[0] + "." # Re-add the dot
        description = parts[1]
        menu_table.add_row(f"[bold white]{number_prefix}[/bold white]", Text(description, style=style))

    menu_panel = Panel(menu_table, title="MENU", border_style="magenta", width=87)
    
    # 7. Recent Transactions Panel Content
    recent_tx_table = Table(show_header=True, header_style="bold green", show_lines=False, padding=(0, 1))
    recent_tx_table.add_column("ID", style="dim", width=4)
    recent_tx_table.add_column("Date", width=10)
    recent_tx_table.add_column("Category", width=12)
    recent_tx_table.add_column("Amount", justify="right", width=10)

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
                category[:12],
                Text(amount_display, style=amount_style)
            )

    recent_tx_panel = Panel(recent_tx_table, title="LAST 10 TRANSACTIONS", border_style="green", width=87)
    
    # 8. Assemble Layout - Stacking all panels vertically
    CONSOLE.print(overview_panel)
    CONSOLE.print(savings_panel)
    CONSOLE.print(menu_panel)
    CONSOLE.print(recent_tx_panel) 

    # 9. Print Message and Prompt
    if message:
        # FIX: Use Text.from_markup() to correctly parse the color tags in the message string
        message_content = Text.from_markup(message)
        CONSOLE.print(Panel(message_content, title="NOTIFICATION", border_style="yellow", width=87))

    return input("\nSelect an option (1-12): ")

# --- Transaction Management Functions ---

def add_transaction():
    """Allows user to add a new income or expense transaction."""
    # We clear here because we are running an interactive input sequence
    CONSOLE.clear()
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
    category = input("Enter Category (e.g., Food, Salary, Rent): ").strip()
    if not category:
        category = "Uncategorized"

    # 4. Get Description
    description = input("Enter short description (optional): ").strip()

    # 5. Get Date
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")

    # 6. Save to DB
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                   (amount, category, description, date_str, transaction_type))
    conn.commit()
    conn.close()

    return f"[bold green]Successfully recorded {transaction_type.upper()} of £{amount:,.2f} under {category}.[/bold green]"

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

    table = Table(title="Transaction History (Latest 50)", title_style="bold yellow", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Date", style="bold white", width=12)
    table.add_column("Category", style="cyan", width=15)
    table.add_column("Description", style="white", width=30)
    table.add_column("Amount", style="bold", justify="right", width=15)
    
    for tid, amount, category, description, date, t_type in transactions:
        amount_display = f"£{amount:,.2f}"
        
        if t_type == 'income':
            amount_style = "bold green"
            amount_display = f"+{amount_display}"
        else: # expense
            amount_style = "bold red"
            amount_display = f"-{amount_display}"
            
        table.add_row(
            str(tid),
            date,
            category,
            description or "---",
            Text(amount_display, style=amount_style)
        )
        
    return table, title

def delete_transaction():
    """Prompts for transaction ID and deletes it."""
    # 1. Show the list of transactions first
    table, title = view_transactions(title="Transactions to Delete")
    show_temporary_view(title, table) # Clears and shows content, then pauses.

    # 2. Get the ID to delete (Note: CONSOLE.clear() is not run here)
    CONSOLE.print(Panel("[bold red]Delete Transaction[/bold red]", border_style="red"))
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
    CONSOLE.clear()
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
    
    # Footer Summary
    final_net = total_monthly_income - total_monthly_expense
    final_net_style = "bold green" if final_net >= 0 else "bold red"
    
    footer = Group(
        table,
        Text("\n" + "="*50),
        Text(f"[green]TOTAL MONTHLY INCOME:  +£{total_monthly_income:,.2f}[/green]"),
        Text(f"[red]TOTAL MONTHLY EXPENSE: -£{total_monthly_expense:,.2f}[/red]"),
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
    
    # Footer Summary
    final_net = total_weekly_income - total_weekly_expense
    final_net_style = "bold green" if final_net >= 0 else "bold red"
    
    footer = Group(
        table,
        Text("\n" + "-"*50),
        Text(f"[green]TOTAL WEEKLY INCOME:  +£{total_weekly_income:,.2f}[/green]"),
        Text(f"[red]TOTAL WEEKLY EXPENSE: -£{total_weekly_expense:,.2f}[/red]"),
        Text(f"WEEKLY NET BALANCE:   £{final_net:,.2f}", style=final_net_style),
        Text("-"*50)
    )
    
    show_temporary_view(title, footer)

def upcoming_calendar():
    """Displays a calendar view for the next 4 weeks showing dates and notes for large expenses."""
    title = "Upcoming Calendar View (4 Weeks)"
    
    # Fetch all transactions that might be bills/major expenses (e.g., > 50)
    conn = sqlite3.connect(DATABASE_EXPENSES)
    cursor = conn.cursor()
    cursor.execute("SELECT amount, description, date FROM transactions WHERE amount > 50 AND type='expense' ORDER BY date ASC")
    major_expenses = cursor.fetchall()
    conn.close()

    now = datetime.datetime.now().date()
    # Find the start of the current week (Monday)
    start_of_week = now - datetime.timedelta(days=now.weekday())
    
    # The calendar table
    calendar_table = Table(title=f"Starting Week of {start_of_week.strftime('%d %b')}", title_style="bold white", show_header=True, header_style="bold yellow", padding=1)
    
    days_of_week = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for day in days_of_week:
        calendar_table.add_column(day, justify="center")

    all_rows = []
    
    # Iterate through 4 weeks (4 rows)
    for week in range(4):
        current_row = []
        for day_offset in range(7):
            current_date = start_of_week + datetime.timedelta(days=(week * 7) + day_offset)
            date_str = current_date.strftime("%Y-%m-%d")
            
            cell_text = Text(current_date.strftime("%d"), style="bold white")
            
            if current_date < now:
                cell_text.style = "dim"
            elif current_date == now:
                cell_text.style = "bold yellow on blue"
                
            # Check for major expenses on this date
            expense_notes = []
            for amount, desc, date in major_expenses:
                if date == date_str:
                    expense_notes.append(f"\n[bold red]-£{amount:,.0f}[/bold red] ({desc[:15]}...)")
                    
            cell_text.append("".join(expense_notes), style="")
            
            current_row.append(cell_text)
        all_rows.append(current_row)

    # Add rows to the table
    for row in all_rows:
        calendar_table.add_row(*row)
    
    content = Group(
        calendar_table,
        Text("\n[bold red]Note:[/bold red] Only expenses > £50 are shown for clarity.")
    )
        
    show_temporary_view(title, content)

# --- Savings Goal Functions ---

def set_savings_goal():
    """Sets a target amount for the savings goal."""
    CONSOLE.clear()
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
    
    CONSOLE.clear()
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
    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, amount, category, description FROM recurring_templates")
    templates = cursor.fetchall()
    conn.close()

    CONSOLE.clear()
    CONSOLE.print(Panel("[bold orange1]Manage Recurring Templates[/bold orange1]", border_style="orange1"))

    if templates:
        table = Table(title="Available Templates", show_header=True, header_style="bold orange1")
        table.add_column("ID", style="dim", width=5)
        table.add_column("Name", style="bold white", width=20)
        table.add_column("Amount", style="red", justify="right")
        table.add_column("Category", style="cyan", width=15)
        table.add_column("Description", style="white", width=30)
        
        for tid, name, amount, category, desc in templates:
            table.add_row(str(tid), name, f"£{amount:,.2f}", category, desc or "---")
        
        CONSOLE.print(table)
    else:
        CONSOLE.print("[yellow]No recurring templates defined yet.[/yellow]")

    # Sub-menu for management
    if templates:
        CONSOLE.print("\n[1] Add New Template | [2] Delete Template | [C] Cancel")
        choice = input("Select an option: ").upper().strip()

        if choice == '1':
            return add_recurring_template()
        elif choice == '2':
            return delete_recurring_template(templates)
        else:
            return "Template management cancelled."
    else:
        # If no templates exist, automatically go to Add, or let them cancel
        CONSOLE.print("\n[1] Add New Template | [C] Cancel")
        choice = input("Select an option: ").upper().strip()
        if choice == '1':
            return add_recurring_template()
        else:
            return "Template management cancelled."


def add_recurring_template():
    """Adds a new recurring template to the settings database."""
    # We clear again if we come from manage_recurring_templates
    CONSOLE.clear()
    CONSOLE.print(Panel("[bold green]Add New Recurring Template (Always recorded as Expense)[/bold green]", border_style="green"))
    
    name = input("Enter Template Name (e.g., Rent, Netflix): ").strip()
    
    while True:
        try:
            amount = float(input("Enter monthly amount (£): "))
            if amount <= 0:
                CONSOLE.print("[bold red]Amount must be positive.[/bold red]")
                continue
            break
        except ValueError:
            CONSOLE.print("[bold red]Invalid number format.[/bold red]")

    category = input("Enter Category: ").strip()
    description = input("Enter description (optional): ").strip()

    conn = sqlite3.connect(DATABASE_SETTINGS)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO recurring_templates (name, amount, category, description) VALUES (?, ?, ?, ?)",
                       (name, amount, category, description))
        conn.commit()
        result_msg = f"[bold green]Template '{name}' added successfully.[/bold green]"
    except sqlite3.IntegrityError:
        result_msg = f"[bold red]Error: Template name '{name}' already exists.[/bold red]"
    finally:
        conn.close()
    
    return result_msg

def delete_recurring_template(templates):
    """Deletes a recurring template by ID."""
    # We clear again if we come from manage_recurring_templates
    CONSOLE.clear()
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
    conn_set = sqlite3.connect(DATABASE_SETTINGS)
    cursor_set = conn_set.cursor()
    cursor_set.execute("SELECT id, name, amount, category, description FROM recurring_templates")
    templates = cursor_set.fetchall()
    conn_set.close()

    if not templates:
        return "[bold red]No recurring templates found. Use option 10 to create one first.[/bold red]"

    CONSOLE.clear()
    CONSOLE.print(Panel("[bold green]Apply Recurring Payment[/bold green]", border_style="green"))
    
    # Display templates for selection
    table = Table(title="Select Template", show_header=True, header_style="bold green")
    table.add_column("ID", style="dim", width=5)
    table.add_column("Name", style="bold white", width=20)
    table.add_column("Amount", style="red", justify="right")
    table.add_column("Category", style="cyan", width=15)
    
    template_map = {}
    for tid, name, amount, category, _ in templates:
        table.add_row(str(tid), name, f"£{amount:,.2f}", category)
        template_map[tid] = (amount, category, name)
    
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

    amount, category, name = template_map[template_id]
    date_str = datetime.datetime.now().strftime("%Y-%m-%d")
    description = f"Recurring payment: {name}"

    # Record the expense transaction
    conn_exp = sqlite3.connect(DATABASE_EXPENSES)
    cursor_exp = conn_exp.cursor()
    cursor_exp.execute("INSERT INTO transactions (amount, category, description, date, type) VALUES (?, ?, ?, ?, ?)",
                       (amount, category, description, date_str, 'expense'))
    conn_exp.commit()
    conn_exp.close()
    
    return f"[bold green]Successfully applied recurring payment '{name}' (Expense: £{amount:,.2f}).[/bold green]"

# --- Main Application Loop ---

def main():
    """The main entry point for the Budget Buddy TUI."""
    initialize_db()
    db_check_and_migrate()
    message = "Welcome to Budget Buddy TUI! Ready for action."

    while True:
        # CRITICAL: Always clear the console before drawing the dashboard
        CONSOLE.clear()
        
        choice = display_dashboard(message)
        message = "" # Reset message after display

        try:
            # We rely on string input for this loop, though some commands expect an int
            if choice.upper() == 'C':
                message = "[yellow]Action cancelled.[/yellow]"
                continue
                
            choice_int = int(choice)
        except ValueError:
            message = "[bold red]Invalid input. Please enter a number between 1 and 12.[/bold red]"
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
        else:
            message = "[bold red]Invalid option. Please enter a number between 1 and 12.[/bold red]"
        
        # The main loop continues, and the first line of the loop will always run CONSOLE.clear() again.

if __name__ == '__main__':
    main()
