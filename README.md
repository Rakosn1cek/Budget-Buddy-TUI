Budget Buddy TUI: Terminal Budget Manager
Budget Buddy TUI is a simple, feature-rich command-line application designed to help you track your personal finances, manage expenses, set savings goals, and monitor your financial health directly from your terminal.
The application uses the rich library for an enhanced Text-User Interface (TUI) experience, providing color-coded, well-formatted tables and dashboards.
Installation and Setup (For Termux on Android)
This section provides the necessary steps for users running the application on Termux (Android).
Prerequisites (Termux)
You must install Python 3 and the core package management tools using the Termux package manager (pkg).
 * Update and Upgrade Termux packages:
   pkg update && pkg upgrade -y

 * Install Python (and Git/Wget if needed):
   pkg install python git wget

How to Get the Code
You have two primary ways to download the budget_budy.py file into your Termux environment:
Option 1: Using wget (Direct Download)
If you have uploaded the file somewhere (like a personal cloud or gist) and have a direct download link (replace [YOUR_DIRECT_URL_HERE]):
wget [YOUR_DIRECT_URL_HERE]/budget_budy.py

Option 2: Using git clone (Recommended for Hosting)
If you host this code in a repository (e.g., GitHub, GitLab), use git clone (replace [YOUR_REPOSITORY_URL]):
git clone [YOUR_REPOSITORY_URL]
cd budget-buddy-tui  # Change to the project directory

Final Installation Steps
 * Install the necessary libraries:
   The application relies on the rich library for its TUI features. Install it using pip.
   pip install rich

 * How to Run
   Navigate to the directory where you saved budget_budy.py in Termux and execute the following command.
   python budget_budy.py

The application will automatically create two SQLite database files (expenses.db and settings.db) on the first run.
Features
 * Financial Overview: Real-time calculation of total income, expenses, and net balance.
 * Transaction Management: Easy addition, viewing, and deletion of both income and expense transactions.
 * Detailed Reporting: Generate detailed Weekly and Monthly summaries broken down by category.
 * Savings Goals: Set a specific savings target and track your progress with a dynamic progress bar.
 * Recurring Payments: Create templates for common bills (like rent or subscriptions) and apply them with a single command.
 * TUI: Visually appealing interface using the rich library for clear, color-coded output.
Updates History
Version 1.1 - Stability and TUI Fixes (Current)
This update focuses on fixing screen rendering issues and ensuring a smooth, reliable terminal experience.
| Change | Description |
|---|---|
| Fixed Dashboard Stacking | Resolved the critical issue where the dashboard would redraw on top of itself, leading to stacked, unreadable output. |
| Centralized TUI Control | All screen clearing and view pauses are now strictly managed by dedicated functions, ensuring perfect terminal state control. |
| Improved Reporting Flow | Reports are displayed in a clean, isolated view before returning control to the main dashboard. |
| Initial Migration | Added logic to check and migrate older database structures (e.g., ensuring the type column exists). |
Version 1.0 - Initial Release (Base Features)
| Change | Description |
|---|---|
| Core Functions | Initial implementation of transaction tracking, saving goals, and basic reports (Weekly/Monthly Summary). |
| Recurring Templates | Added the ability to create and apply recurring payment templates. |
| Rich TUI | Implemented the full dashboard layout using rich panels, tables, and progress bars. |
For Linux and macOS Terminal Users
The steps are very similar, using your system's default package manager (like apt or brew) to install Python.
 * Ensure Python and Git are installed:
   # On Debian/Ubuntu Linux:
sudo apt update
sudo apt install python3 python3-pip git

# On macOS (using Homebrew):
brew install python git

 * Get the code:
   If you have hosted the repository, clone it here (replace [YOUR_REPOSITORY_URL]):
   git clone [YOUR_REPOSITORY_URL]
cd budget-buddy-tui

 * Install the Python dependency (rich):
   pip install rich

 * Run the script:
   python budget_budy.py

   (Note: Some systems may require python3 instead of python.)

