Budget Buddy TUI
A comprehensive, terminal-based personal budget and finance tracker built in Python using the rich library for a modern, colorful Text User Interface (TUI). This application uses SQLite for reliable, persistent data storage.
Features
Budget Buddy TUI has evolved into a full-featured financial management tool, including:
Core Transactions & Data
Absolute Pathing: Data is stored persistently in ~/Budget-Buddy-TUI/expenses.db and ~/Budget-Buddy-TUI/settings.db, ensuring the application works correctly no matter which directory it's run from.
Dual Transaction Types: Record both Income (I) and Expense (E).
Detailed Logging: Transactions include amount, category, description, and the ability to input the date in DD-MM-YYYY format (defaults to today).
Filtering: Filter transactions easily by specific category (Option 3).
Category Management (NEW): View, add, and safely delete custom categories (Option 13). When deleting a category, associated transactions are automatically recategorized to "Uncategorized."
Recurring Payments & Automation
Recurring Templates (NEW): Create, manage, and delete templates for recurring monthly expenses (e.g., Rent, Bills, Subscriptions).
Due Day Tracking: Each template specifies a "Due Day" (1-31) for accurate scheduling.
Automated Application (NEW): On startup, the app automatically checks for and records any recurring payment that is due today and has not yet been applied this month.
Manual Application: Manually apply a template to record an expense (Option 11).
Reporting & Planning
Financial Dashboard: Provides an instant overview of Total Income, Total Expenses, and Net Balance (All Time).
Weekly Summary (NEW): Generate a categorized breakdown of income and expenses for the current Monday-to-Sunday week (Option 4).
Monthly Detailed Summary (NEW): Provides a comprehensive breakdown of Income, Expenses, and Net values per category for the current month (Option 5).
Upcoming Calendar (NEW): Displays a calendar view of the current week, highlighting today's date and showing reminders for due recurring payments and recent major expenses (Option 6).
Savings Goal Tracking
Set Goal Target: Define a target amount for a personal savings goal (Option 8).
Track Progress: The dashboard displays the progress toward the goal target.
Add to Savings: Easily transfer funds from your net balance to your savings goal. This transfer is automatically recorded as an Expense under the "Savings Transfer" category to keep your primary balance accurate (Option 9).
Setup and Running
Prerequisites
Python 3.x
rich library for the TUI interface.
Installation
Clone the repository:
git clone [Your-Repo-URL] ~/Budget-Buddy-TUI
cd ~/Budget-Buddy-TUI


Install dependencies:
pip install rich


Set up the Alias (bb): Add the following line to your shell's configuration file (e.g., ~/.bashrc, ~/.zshrc):
# Budget Buddy Alias
alias bb='python3 ~/Budget-Buddy-TUI/budget_budy.py'


Reload your shell configuration:
source ~/.bashrc  # or source ~/.zshrc


Usage
Run the application from any directory using the alias:
bb


The application will launch and load your data automatically from ~/Budget-Buddy-TUI/expenses.db and ~/Budget-Buddy-TUI/settings.db.
