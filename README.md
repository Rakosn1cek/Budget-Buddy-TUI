Budget Buddy TUI (Termux Expense Tracker)
​A simple, terminal-based personal finance tracker written in Python 3.12, designed for use in environments like Termux on Android. It uses sqlite3 for persistence and the rich library for a nice Text User Interface (TUI).

​Status:

​Feature Complete: All core functionality (tracking, summaries, goals, recurring payments) is implemented.

Stable: Specifically configured to run reliably on Termux's standard Python 3.12 environment without complex build dependencies.

​Features:

​Track income (positive amounts) and expenses (negative amounts).

​Real-time balance and expense/income overview.

​Set and track a single savings goal with a progress bar.

​Monthly recurring transaction templates (e.g., rent, subscriptions).

​Weekly and Monthly summary reports categorized by spending.

​Transaction filtering and deletion by ID.

​Installation (In Termux):

1.Install Python and Git:

pkg update && pkg upgrade -y

pkg install python git -y

2.Clone the Repository:

git clone [https://github.com/Rakosn1cek/Budget-Buddy-TUI.git](https://github.com/Rakosn1cek/Budget-Buddy-TUI.git)

cd Budget-Buddy-TUI

3.Install Dependencies:

pip install rich

4.Run the application:

python budget_budy.py

(Alternatively, use the alias setup:

alias bb='python ~/Budget-Buddy-TUI/budget_budy.py'

)


Contributing:

​Contributions are welcome! 
If you have an idea for a new feature, a bug report, or a code improvement, please feel free to:

​Open an Issue: Describe the bug or feature request clearly.

​Submit a Pull Request: If you've written code, please fork the repository and submit a PR with your changes. Focus areas include improved reporting, data export functionality, or adding command-line arguments.

​License:

​This project is licensed under the MIT License - see the LICENSE.txt file for details

