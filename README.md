💰 Budget Buddy TUI 💰
A comprehensive, terminal-based personal budget and finance tracker built in Python using the rich library for a modern, colorful Text User Interface (TUI).
✨ Features at a Glance
Category
Feature
Description
Data & Core
Persistent Storage
Data is stored safely in fixed paths (~/Budget-Buddy-TUI/).


Income & Expense
Record both income (I) and expenses (E) with detailed tracking.


Category Management
✅ Add, view, and safely delete custom categories.
Reporting & Planning
Dashboard Overview
Instant Net Balance, Total Income, and Total Expense snapshot.


Weekly/Monthly Reports
Detailed, categorized summaries for your current week and month.


Upcoming Calendar
📅 View a calendar highlighting due dates for bills and major expenses.
Automation & Savings
Recurring Templates
Set up templates with a defined Due Day (1-31) for easy bill tracking.


Auto-Apply Payments
Automatically records recurring payments on their due day upon startup.


Savings Goal
Track progress toward a custom savings target and transfer funds from your balance.

🛠️ Setup and Running
Prerequisites
Python 3.x
rich library (install via pip install rich)
🚀 Installation and Alias
The application is designed to be run from any directory via a simple alias, ensuring data integrity.
# 1. Clone the repository into the dedicated data folder:
git clone [Your-Repo-URL] ~/Budget-Buddy-TUI
cd ~/Budget-Buddy-TUI

# 2. Install the rich dependency:
pip install rich


🔗 Configure Alias
Add the following line to your shell's configuration file (e.g., ~/.bashrc, ~/.zshrc):
# Budget Buddy Alias
alias bb='python3 ~/Budget-Buddy-TUI/budget_budy.py'


Then, reload your shell configuration:
source ~/.bashrc  # or source ~/.zshrc


▶️ Usage
Run the application from anywhere:
bb


