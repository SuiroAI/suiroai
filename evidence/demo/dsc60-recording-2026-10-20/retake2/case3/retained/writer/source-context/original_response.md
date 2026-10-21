Order **883 product units across 113 products at stores** for the week of December 1–7, 2025, using **restocking.csv**. The list covers all 12 stores and includes 223 products at stores needing no additional order. Quantities cover supplier delivery time plus the following weekly review period, while keeping the required spare stock and pack sizes.

**Review the 52 flagged products at stores first:** stock may run short before a new order arrives. Consider faster delivery or a transfer. Seven have zero additional orders because incoming deliveries cover the total need but may arrive too late; check their flagged dates before accepting the zero. Incoming deliveries match the stock records.

The reusable routine now prepares sales, estimates needs, subtracts usable stock and timely deliveries, applies ordering rules, and produces the list and warnings. The measured local weekly calculation took **0.83 seconds**, using little memory for an ordinary computer. It runs without ChatGPT or other language-model calls.

It averages recent sales and shares some information across stores. On the same October–November checks, its errors were about **2% lower** than a simple recent-average baseline—a small difference, not demonstrated business improvement. Your actual current method was not supplied for comparison.

Past sales cannot reveal purchases missed when shelves were empty, so review flagged shortages and refresh the files weekly. The command can be scheduled on your computer with ChatGPT’s help setting it up; no schedule is installed.
