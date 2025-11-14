# budget_budy.py
# A simple, Python 3.12 compatible TUI Expense Tracker for Termux.
# Uses built-in sqlite3 for persistence and the 'rich' library for a nice TUI.

import sqlite3
import sys
import os
from datetime import datetime, timedelta
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.columns import Columns

# --- Configuration ---
DB_NAME = 'expenses.db'
SETTINGS_DB = 'settings.db'
CURRENCY_SYMBOL = '£' # UK Pound Sterling (Localized)
console = Console()

# --- Database Setup ---

def initialize_database():
    """Ensures the SQLite database and expense tables exist."""
    try:
        # Initialize Expenses DB
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT
            );
        ''')
        
        # Initialize Settings DB (for goals)
        settings_conn = sqlite3.connect(SETTINGS_DB)
        settings_cursor = settings_conn.cursor()
        settings_cursor.execute('''
            CREATE TABLE IF NOT EXISTS goals (
                name TEXT PRIMARY KEY,
                target_amount REAL NOT NULL,
                current_savings REAL NOT NULL DEFAULT 0.0
            );
        ''')
        
        # Initialize Recurring Transactions DB
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recurring_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                day_of_month INTEGER NOT NULL, -- Day of month to pay (1-28)
                last_added TEXT -- Date last added to expenses
            );
        ''')
        
        conn.commit()
        settings_conn.commit()
        settings_conn.close()

        return conn
    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}", style="bold red")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Initialization Error:[/bold red] {e}", style="bold red")
        sys.exit(1)

# --- Goal Management Functions ---

def get_savings_goal():
    """Retrieves the current savings goal and current savings."""
    settings_conn = sqlite3.connect(SETTINGS_DB)
    cursor = settings_conn.cursor()
    cursor.execute("SELECT target_amount, current_savings FROM goals WHERE name = 'primary_goal'")
    result = cursor.fetchone()
    settings_conn.close()

    if result:
        return result[0], result[1]
    return 0.0, 0.0

def set_savings_goal():
    """Allows the user to set a new savings goal target."""
    console.print(Panel("[bold yellow]Set or Update Savings Goal[/bold yellow]", border_style="yellow"))

    while True:
        # Uses .format() for universal compatibility
        prompt_text = "[bold cyan]Target Goal Amount ({0}):[/bold cyan] ".format(CURRENCY_SYMBOL)
        target_str = console.input(prompt_text).strip()
        try:
            target = float(target_str)
            if target <= 0:
                 console.print("[bold red]Target must be a positive number.[/bold red]")
                 continue
            break
        except ValueError:
            console.print("[bold red]Invalid amount. Please enter a valid number.[/bold red]")

    # Get current savings, since we only want to update the target
    _, current_savings = get_savings_goal()

    try:
        settings_conn = sqlite3.connect(SETTINGS_DB)
        cursor = settings_conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO goals (name, target_amount, current_savings) VALUES (?, ?, ?)",
            ('primary_goal', target, current_savings)
        )
        settings_conn.commit()
        settings_conn.close()
        console.print(f"\n[bold green]Success! Savings goal set to {CURRENCY_SYMBOL}{target:,.2f}.[/bold green]")
    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}", style="bold red")

def add_to_savings():
    """Allows the user to manually add to the current savings amount."""
    target, current = get_savings_goal()
    if target == 0.0:
        console.print(Panel("[bold yellow]No savings goal is currently set. Set one first (Menu Option 8).[/bold yellow]"))
        return

    console.print(Panel("[bold yellow]Manually Add to Current Savings[/bold yellow]", border_style="yellow"))

    while True:
        # Uses .format() for universal compatibility
        prompt_text = "[bold cyan]Amount to add to savings ({0}):[/bold cyan] ".format(CURRENCY_SYMBOL)
        amount_str = console.input(prompt_text).strip()
        try:
            amount = float(amount_str)
            if amount <= 0:
                 console.print("[bold red]Amount must be positive.[/bold red]")
                 continue
            break
        except ValueError:
            console.print("[bold red]Invalid amount. Please enter a valid number.[/bold red]")

    new_savings = current + amount

    try:
        settings_conn = sqlite3.connect(SETTINGS_DB)
        cursor = settings_conn.cursor()
        cursor.execute(
            "UPDATE goals SET current_savings = ? WHERE name = 'primary_goal'",
            (new_savings,)
        )
        settings_conn.commit()
        settings_conn.close()
        console.print(f"\n[bold green]Success! Added {CURRENCY_SYMBOL}{amount:,.2f} to savings. New total: {CURRENCY_SYMBOL}{new_savings:,.2f}.[/bold green]")
    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}", style="bold red")


def make_goal_progress_panel(target, current):
    """Creates a stable, static progress bar for the savings goal."""
    if target == 0.0:
        return Panel(
            Text("No Savings Goal Set. Use option 8 to set one!", style="bold yellow"),
            title="[bold red]SAVINGS GOAL[/bold red]",
            border_style="red"
        )
    
    progress_ratio = min(1.0, current / target) if target > 0 else 0.0
    
    # Define bar style and length - AGGRESSIVELY REDUCED TO 12 FOR TERMINAL COMPATIBILITY
    bar_length = 12
    fill_chars = int(bar_length * progress_ratio)
    empty_chars = bar_length - fill_chars
    
    if progress_ratio >= 1.0:
        bar_style = "bold green"
        # Full bar, no empty chars
        bar_text = f"[{bar_style}]|{'=' * bar_length}|[/]"
    elif progress_ratio > 0.5:
        bar_style = "bold yellow"
        # Partial bar, uses '-' for empty space
        bar_text = f"[{bar_style}]|{'=' * fill_chars}{'-' * empty_chars}|[/]"
    else:
        bar_style = "bold cyan"
        # Minimal bar
        bar_text = f"[{bar_style}]|{'=' * fill_chars}{'-' * empty_chars}|[/]"

    percentage = progress_ratio * 100
    
    # Build the final content using Text.from_markup() for reliable markup parsing
    
    # Determine goal status
    status_style = ""
    if current >= target:
        status_text = "[bold green]:trophy: GOAL ACHIEVED! :trophy:[/bold green]"
        status_style = "bold green"
    elif progress_ratio > 0.5:
        status_text = "[bold yellow]Over halfway there![/bold yellow]"
        status_style = "bold yellow"
    else:
        status_text = "[bold cyan]Keep saving![/bold cyan]"
        status_style = "bold cyan"
        
    
    # Build the final content using Text.from_markup() for reliable markup parsing
    content = Text.from_markup(
        f"Saved: {CURRENCY_SYMBOL}{current:,.0f} / {CURRENCY_SYMBOL}{target:,.0f}\n"
        f"{bar_text} {percentage:3.0f}%\n"
        f"{status_text}",
        style="bold white"
    )


    return Panel(
        content,
        title="[bold yellow]SAVINGS GOAL[/bold yellow]",
        border_style=status_style
    )

# --- Transaction Functions ---

def get_balance(conn):
    """Calculates the total balance of all transactions."""
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM expenses;")
    result = cursor.fetchone()
    total = result[0] if result and result[0] is not None else 0.0
    return total

def get_spending_summary(conn):
    """Calculates total expense and income across all time."""
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE amount < 0;")
    total_expenses = cursor.fetchone()[0] or 0.0
    cursor.execute("SELECT SUM(amount) FROM expenses WHERE amount > 0;")
    total_income = cursor.fetchone()[0] or 0.0
    
    return total_income, abs(total_expenses)

def add_transaction(conn):
    """Prompts user to add a new transaction."""
    console.print(Panel("[bold yellow]Add New Transaction[/bold yellow]", border_style="yellow"))
    
    while True:
        amount_str = console.input(f"[bold cyan]Amount (e.g., -15.50 for expense, 100 for income):[/bold cyan] ").strip()
        try:
            amount = float(amount_str)
            break
        except ValueError:
            console.print("[bold red]Invalid amount. Please enter a valid number.[/bold red]")
            
    category = console.input("[bold cyan]Category (e.g., Food, Income, Transport):[/bold cyan] ").strip()
    if not category:
        category = "General"
    
    description = console.input("[bold cyan]Description (optional):[/bold cyan] ").strip()
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO expenses (date, amount, category, description) VALUES (?, ?, ?, ?)",
            (date, amount, category, description)
        )
        conn.commit()
        console.print(f"\n[bold green]Success! Added {CURRENCY_SYMBOL}{amount:,.2f} under {category}.[/bold green]")
    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error during insertion:[/bold red] {e}", style="bold red")

def delete_transaction(conn):
    """Prompts user to delete a transaction by ID."""
    console.print(Panel("[bold red]Delete Transaction[/bold red]", border_style="red"))
    
    # First, display recent transactions so the user knows the IDs
    view_expenses(conn, limit=50) # Show more recent transactions for deletion

    while True:
        id_str = console.input("[bold red]Enter the ID of the transaction to DELETE (or 'c' to cancel):[/bold red] ").strip()
        if id_str.lower() == 'c':
            console.print("[bold yellow]Deletion cancelled.[/bold yellow]")
            return

        try:
            trans_id = int(id_str)
            break
        except ValueError:
            console.print("[bold red]Invalid ID. Please enter a valid number or 'c'.[/bold red]")
            continue

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM expenses WHERE id = ?", (trans_id,))
        if cursor.fetchone() is None:
            console.print(f"[bold yellow]Warning: Transaction ID {trans_id} not found.[/bold yellow]")
            return
            
        # Confirmation step (basic console confirmation)
        confirm = console.input(f"[bold red]Are you sure you want to delete ID {trans_id}? (YES/no):[/bold red] ").strip().lower()
        
        if confirm == 'yes' or confirm == 'y':
            cursor.execute("DELETE FROM expenses WHERE id = ?", (trans_id,))
            conn.commit()
            console.print(f"\n[bold green]Success! Transaction ID {trans_id} deleted.[/bold green]")
        else:
            console.print("[bold yellow]Deletion cancelled by user.[/bold yellow]")

    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error during deletion:[/bold red] {e}", style="bold red")

def add_recurring_template(conn):
    """Allows the user to create a template for a monthly recurring transaction."""
    console.print(Panel("[bold yellow]Add New Recurring Template[/bold yellow]", border_style="yellow"))

    name = console.input("[bold cyan]Template Name (e.g., Rent, Netflix):[/bold cyan] ").strip()
    if not name:
        console.print("[bold red]Template creation cancelled.[/bold red]")
        return

    while True:
        amount_str = console.input(f"[bold cyan]Amount ({CURRENCY_SYMBOL}, e.g., -50.00 for bill, 1500 for salary):[/bold cyan] ").strip()
        try:
            amount = float(amount_str)
            break
        except ValueError:
            console.print("[bold red]Invalid amount. Please enter a valid number.[/bold red]")

    category = console.input("[bold cyan]Category (e.g., Housing, Subscription, Income):[/bold cyan] ").strip()
    if not category:
        category = "General"

    while True:
        day_str = console.input("[bold cyan]Payment Day of the Month (1-28):[/bold cyan] ").strip()
        try:
            day_of_month = int(day_str)
            if 1 <= day_of_month <= 28:
                break
            else:
                console.print("[bold red]Day must be between 1 and 28.[/bold red]")
        except ValueError:
            console.print("[bold red]Invalid day. Enter a number.[/bold red]")

    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO recurring_transactions (name, amount, category, day_of_month) VALUES (?, ?, ?, ?)",
            (name, amount, category, day_of_month)
        )
        conn.commit()
        console.print(f"\n[bold green]Success! Template '{name}' added. Due day: {day_of_month}.[/bold green]")
    except sqlite3.IntegrityError:
        console.print(f"[bold red]Error: Template name '{name}' already exists.[/bold red]")
    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}", style="bold red")


def apply_recurring_template(conn):
    """Adds a recurring transaction to expenses for the current date."""
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, amount, category, day_of_month, last_added FROM recurring_transactions")
    templates = cursor.fetchall()

    if not templates:
        console.print(Panel("[bold yellow]No recurring templates found. Use option 10 to add one.[/bold yellow]"))
        return

    console.print(Panel("[bold yellow]Apply Recurring Templates[/bold yellow]", border_style="yellow"))

    template_table = Table(title="[bold magenta]Available Templates[/bold magenta]", show_header=True, header_style="bold cyan reverse")
    template_table.add_column("ID", style="dim", width=4)
    template_table.add_column("Name", style="yellow")
    template_table.add_column("Amount", justify="right")
    template_table.add_column("Day", style="cyan", width=5)

    template_map = {}
    for t_id, name, amount, category, day, last_added in templates:
        template_map[str(t_id)] = (name, amount, category, day)
        amount_color = "red" if amount < 0 else "green"
        template_table.add_row(
            str(t_id),
            name,
            f"[{amount_color}]{CURRENCY_SYMBOL}{amount:,.2f}[/]",
            str(day)
        )

    console.print(template_table)

    while True:
        choice = console.input("[bold cyan]Enter Template ID to apply (or 'c' to cancel):[/bold cyan] ").strip()
        if choice.lower() == 'c':
            console.print("[bold yellow]Operation cancelled.[/bold yellow]")
            return

        if choice in template_map:
            name, amount, category, day = template_map[choice]
            break
        else:
            console.print("[bold red]Invalid Template ID.[/bold red]")

    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        # 1. Add to expenses
        cursor.execute(
            "INSERT INTO expenses (date, amount, category, description) VALUES (?, ?, ?, ?)",
            (date, amount, category, f"Recurring: {name}")
        )
        # 2. Update last_added timestamp in template
        cursor.execute(
            "UPDATE recurring_transactions SET last_added = ? WHERE id = ?",
            (date, choice)
        )
        conn.commit()
        console.print(f"\n[bold green]Success! Recurring transaction '{name}' added to expenses.[/bold green]")
    except sqlite3.Error as e:
        console.print(f"[bold red]Database Error:[/bold red] {e}", style="bold red")


def view_recurring_calendar(conn):
    """Displays a calendar view of upcoming recurring payments for the next 30 days."""
    
    cursor = conn.cursor()
    cursor.execute("SELECT name, amount, category, day_of_month FROM recurring_transactions ORDER BY day_of_month ASC")
    templates = cursor.fetchall()
    
    if not templates:
        console.print(Panel("[bold yellow]No recurring templates found. Use option 10 to add one.[/bold yellow]"))
        return

    now = datetime.now()
    today = now.day
    current_month = now.month
    current_year = now.year
    
    # Calculate upcoming dates for the next 30 days
    upcoming_payments = []
    
    for name, amount, category, day in templates:
        
        # Determine the next payment date for the current month or next month
        target_year = current_year
        target_month = current_month
        
        # If the recurring day is before today, assume the next payment is next month
        if day < today:
            target_month += 1
            if target_month > 12:
                target_month = 1
                target_year += 1
        
        # Build the next payment date (clamping day to 28 for stability)
        try:
            next_date = datetime(target_year, target_month, day)
        except ValueError:
            # Handle potential date errors gracefully
            continue
            
        # Only show dates within the next 30 days and not before today
        if next_date <= (now + timedelta(days=30)) and next_date >= now:
            upcoming_payments.append({
                "date": next_date,
                "name": name,
                "amount": amount,
                "category": category,
            })

    # --- CALENDAR DISPLAY ---
    
    upcoming_payments.sort(key=lambda x: x['date'])

    table = Table(title=f"[bold blue]Upcoming Payments Calendar (Next 30 Days)[/bold blue]", show_header=True, header_style="bold magenta reverse")
    table.add_column("Date", style="cyan", width=12)
    table.add_column("Day Remaining", style="dim", width=12)
    table.add_column("Template", style="yellow", width=15)
    table.add_column("Category", style="green", width=15)
    table.add_column("Amount", justify="right")

    for payment in upcoming_payments:
        amount_color = "red" if payment['amount'] < 0 else "green"
        days_remaining = (payment['date'] - now).days + 1 # Include today
        
        table.add_row(
            payment['date'].strftime('%Y-%m-%d'),
            f"[bold]{days_remaining}[/] days",
            payment['name'],
            payment['category'],
            f"[{amount_color}]{CURRENCY_SYMBOL}{abs(payment['amount']):,.2f}[/]"
        )
    
    if not upcoming_payments:
        console.print(Panel("[bold green]No bills due in the next 30 days.[/bold green]"))

    else:
        console.print(table)


def view_expenses(conn, limit=15):
    """Displays the last N expenses in a formatted table."""
    cursor = conn.cursor()
    cursor.execute(f"SELECT id, date, amount, category, description FROM expenses ORDER BY date DESC LIMIT {limit};")
    rows = cursor.fetchall()
    
    if not rows:
        console.print(Panel("[bold yellow]No transactions recorded yet.[/bold yellow]"))
        return

    table = Table(title="[bold blue]Recent Transactions[/bold blue]", show_header=True, header_style="bold magenta reverse")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Date", style="cyan", width=12)
    table.add_column("Amount", style="white", justify="right")
    table.add_column("Category", style="green")
    table.add_column("Description", style="yellow")

    for row in rows:
        amount_val = row[2]
        amount_color = "red" if amount_val < 0 else "green"
        
        # Format date to show only YYYY-MM-DD
        date_str = row[1].split(' ')[0] 
        
        table.add_row(
            str(row[0]),
            date_str,
            f"[{amount_color}]{CURRENCY_SYMBOL}{abs(amount_val):,.2f}[/]",
            row[3],
            row[4] if row[4] else "[dim grey](N/A)[/]"
        )
    
    console.print(table)

def view_expenses_by_category(conn):
    """Prompts user for a category and displays matching transactions."""
    console.print(Panel("[bold yellow]Filter Transactions by Category[/bold yellow]", border_style="yellow"))

    category_filter = console.input("[bold cyan]Enter Category to filter by (e.g., Food, Income):[/bold cyan] ").strip()
    if not category_filter:
        console.print("[bold red]Filter cancelled.[/bold red]")
        console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        return

    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, date, amount, category, description FROM expenses WHERE category LIKE ? ORDER BY date DESC",
        (f'%{category_filter}%',)
    )
    rows = cursor.fetchall()

    if not rows:
        console.print(Panel(f"[bold yellow]No transactions found for category '{category_filter}'.[/bold yellow]"))
        return

    table = Table(title=f"[bold blue]Transactions for '{category_filter}'[/bold blue]", show_header=True, header_style="bold magenta reverse")
    table.add_column("ID", style="dim", width=4)
    table.add_column("Date", style="cyan", width=12)
    table.add_column("Amount", style="white", justify="right")
    table.add_column("Category", style="green")
    table.add_column("Description", style="yellow")

    total_amount = 0.0
    for row in rows:
        amount_val = row[2]
        total_amount += amount_val
        amount_color = "red" if amount_val < 0 else "green"
        date_str = row[1].split(' ')[0] 
        
        table.add_row(
            str(row[0]),
            date_str,
            f"[{amount_color}]{CURRENCY_SYMBOL}{abs(amount_val):,.2f}[/]",
            row[3],
            row[4] if row[4] else "[dim grey](N/A)[/]"
        )
    
    # Add Total for Filtered Results
    total_color = "bold green" if total_amount >= 0 else "bold red"
    table.add_section()
    table.add_row(
        "[bold white]TOTAL (Filtered)[/bold white]", 
        "",
        f"[{total_color}]{CURRENCY_SYMBOL}{total_amount:,.2f}[/]",
        "",
        ""
    )

    console.print(table)

def view_summary_report(conn, time_period):
    """
    Calculates and displays a detailed summary of spending and income
    by category for a given time period ('week' or 'month').
    """
    
    now = datetime.now()
    start_date = None
    title = ""

    if time_period == 'week':
        # Calculate start of the week (Monday)
        start_date = now - timedelta(days=now.weekday())
        start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
        title = f"[bold blue]Summary: Current Week[/bold blue] (Starting {start_date.strftime('%Y-%m-%d')})"
    
    elif time_period == 'month':
        # Calculate start of the month
        start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        title = f"[bold blue]Summary: Current Month[/bold blue] ({now.strftime('%Y-%m')})"
    
    else:
        return

    start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')

    cursor = conn.cursor()
    # Query for all transactions since the start date
    cursor.execute(
        "SELECT amount, category FROM expenses WHERE date >= ?",
        (start_date_str,)
    )
    rows = cursor.fetchall()

    if not rows:
        console.print(Panel(f"[bold yellow]No transactions recorded this {time_period}.[/bold yellow]"))
        return

    # Aggregate data
    total_spent = 0.0
    total_income = 0.0
    category_summary = {}

    for amount, category in rows:
        if amount < 0:
            total_spent += amount
            flow_type = "Expense"
        else:
            total_income += amount
            flow_type = "Income"
        
        # Group by flow type and category
        key = (flow_type, category)
        category_summary[key] = category_summary.get(key, 0.0) + amount


    # --- CATEGORY BREAKDOWN TABLE ---
    summary_table = Table(title=title, show_header=True, header_style="bold cyan reverse")
    summary_table.add_column("Flow", style="dim", width=8)
    summary_table.add_column("Category", style="yellow")
    summary_table.add_column("Amount", justify="right")
    
    # Sort categories for cleaner display (descending by absolute value)
    sorted_categories = sorted(
        category_summary.items(),
        key=lambda item: abs(item[1]),
        reverse=True
    )
    
    for (flow_type, category), amount in sorted_categories:
        amount_color = "red" if flow_type == "Expense" else "green"
        flow_style = "bold red" if flow_type == "Expense" else "bold green"
        
        summary_table.add_row(
            Text(flow_type, style=flow_style),
            category,
            f"[{amount_color}]{CURRENCY_SYMBOL}{amount:,.2f}[/]"
        )

    # --- TOTALS ROW ---
    summary_table.add_section()
    summary_table.add_row(
        "[bold white]NET FLOW[/bold white]",
        "",
        f"[bold white]{CURRENCY_SYMBOL}{(total_income + total_spent):,.2f}[/]"
    )
    summary_table.add_row(
        "[bold red]TOTAL EXPENSE[/bold red]",
        "",
        f"[bold red]{CURRENCY_SYMBOL}{abs(total_spent):,.2f}[/]"
    )
    summary_table.add_row(
        "[bold green]TOTAL INCOME[/bold green]",
        "",
        f"[bold green]{CURRENCY_SYMBOL}{total_income:,.2f}[/]"
    )

    console.print(summary_table)


def make_dashboard(conn):
    """Creates the main TUI dashboard layout."""
    
    balance = get_balance(conn)
    income, expense = get_spending_summary(conn)
    target, current = get_savings_goal()

    layout = Layout(name="root")
    
    # 1. Header (Title)
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body")
    )
    
    # 2. Body split into Balance and Menu
    layout["body"].split_row(
        Layout(name="left_column", ratio=1),
        Layout(name="right_column", ratio=1)
    )
    
    # 3. Left Column split into Financial Overview and Goal Progress
    # FIX: Using split() ensures the goal panel takes the rest of the space.
    layout["left_column"].split(
        Layout(name="balance_panel", size=10),
        Layout(name="goal_panel") 
    )


    # --- HEADER CONTENT (WITH DATE/TIME FIX) ---
    current_time_str = datetime.now().strftime('%A, %d %b %Y | %H:%M')
    header_content = Columns(
        [
            Text("BUDGET BUDDY TUI", justify="left", style="bold white on blue"),
            Text(current_time_str, justify="right", style="bold white on blue")
        ]
    )
    
    layout["header"].update(
        Panel(
            header_content,
            style="bold blue"
        )
    )

    # --- BALANCE PANEL CONTENT ---
    balance_style = "bold green" if balance >= 0 else "bold red"
    
    balance_table = Table(box=None, show_header=False)
    balance_table.add_column("Key", style="dim")
    balance_table.add_column("Value", justify="right")
    
    balance_table.add_row(
        Text("Total Income:", style="green"), 
        Text(f"+{CURRENCY_SYMBOL}{income:,.2f}", style="bold green")
    )
    balance_table.add_row(
        Text("Total Expenses:", style="red"), 
        Text(f"-{CURRENCY_SYMBOL}{expense:,.2f}", style="bold red")
    )
    balance_table.add_row(
        Text("NET BALANCE:", style="bold white"), 
        Text(f"{CURRENCY_SYMBOL}{balance:,.2f}", style=balance_style)
    )

    layout["balance_panel"].update(
        Panel(
            balance_table,
            title="[bold yellow]FINANCIAL OVERVIEW (All Time)[/bold yellow]",
            border_style="cyan"
        )
    )
    
    # --- GOAL PANEL CONTENT ---
    target, current = get_savings_goal()
    layout["goal_panel"].update(make_goal_progress_panel(target, current))


    # --- MENU PANEL CONTENT (WITH EMOJI/ALIGNMENT FIXES) ---
    menu = (
        "[bold white]1.[/bold white] :heavy_plus_sign: Add Transaction\n"
        "[bold white]2.[/bold white] :page_with_curl: View Recent Expenses\n"
        "[bold white]3.[/bold white] :mag:  [cyan]Filter by Category[/cyan]\n"
        "[bold white]4.[/bold white] :calendar: [green]Weekly Summary[/green]\n"
        "[bold white]5.[/bold white] :date: [magenta]Monthly Detailed Summary[/magenta]\n"
        "[bold white]6.[/bold white] :date: [yellow]Upcoming Calendar[/yellow]\n"
        "[bold white]7.[/bold white] :cross_mark: [red]Delete Transaction[/red]\n"
        "[bold white]8.[/bold white] :star: [yellow]Set Savings Goal[/yellow]\n"
        "[bold white]9.[/bold white] £ [cyan]Add to Savings[/cyan]\n"
        "[bold white]10.[/bold white] :bookmark: [yellow]Recurring Templates[/yellow]\n"
        "[bold white]11.[/bold white] :paperclip: [green]Apply Template[/green]\n"
        "[bold white]12.[/bold white] :door: Exit Application\n\n"
    )
    
    layout["right_column"].update(
        Panel(
            menu,
            title="[bold yellow]MENU[/bold yellow]",
            border_style="magenta"
        )
    )
    
    return layout

def main_menu(conn):
    """Displays the main menu and handles user input."""
    
    while True:
        console.clear()
        
        # Display the TUI Dashboard
        console.print(make_dashboard(conn))

        choice = console.input("\n[bold magenta]Select an option (1-12):[/bold magenta] ").strip()

        if choice == '1':
            add_transaction(conn)
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '2':
            view_expenses(conn)
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '3':
            view_expenses_by_category(conn)
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '4':
            view_summary_report(conn, 'week')
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '5':
            view_summary_report(conn, 'month')
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '6':
            view_recurring_calendar(conn)
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '7':
            delete_transaction(conn)
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '8':
            set_savings_goal()
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '9':
            add_to_savings()
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '10':
            add_recurring_template(conn)
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '11':
            apply_recurring_template(conn)
            console.input("[bold cyan]\nPress Enter to return to the dashboard...[/bold cyan]")
        elif choice == '12':
            console.print(Panel("[bold yellow]Thank you for using Budget Buddy. Goodbye![/bold yellow]"))
            break
        else:
            console.print("[bold red]Invalid choice. Please select 1 through 12.[/bold red]")
            console.input("[bold cyan]\nPress Enter to continue...[/bold cyan]")


if __name__ == "__main__":
    # 1. Check for required library 'rich' (precautionary check)
    try:
        import rich
    except ImportError:
        console.print(Panel(
            "[bold red]FATAL ERROR: Missing 'rich' library.[/bold red]\n"
            "[yellow]To fix this, please run the following command in Termux:[/yellow]\n\n"
            "[bold green]pip install rich[/bold green]",
            title="[red]Installation Required[/red]",
            border_style="red"
        ))
        sys.exit(1)
        
    # 2. Start application
    db_connection = initialize_database()
    main_menu(db_connection)
    db_connection.close()
