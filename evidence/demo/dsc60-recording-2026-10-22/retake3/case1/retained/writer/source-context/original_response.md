Order **875 units across 111 products at stores** for the week of December 1–7, 2025, using `restocking.csv`. The list also includes **225 zero orders** where stock and incoming deliveries cover the supplied rules.

Review the **52 shortage flags first**: those items may run short before a new order arrives, so check faster supply options. Incoming deliveries match the stock records. Orders cover supplier delivery time plus the following weekly review period; safety stock, minimum orders and pack sizes explain why some quantities exceed expected weekly sales.

The reusable weekly routine now loads and cleans sales, estimates purchasing needs, subtracts stock and incoming deliveries, applies your ordering rules, and exports the list with timing warnings. Its local weekly calculation took **0.9 seconds** on this computer. The observed workload fits comfortably on an ordinary computer for these files.

The chosen method estimates purchase sizes and gaps between purchases. Across eight October–November weekly comparisons, its next-week errors were about **2% lower** than a simple recent-average baseline—a small advantage. Your exact buying formula was not specified, so this does not establish improvement over your own process.

Estimates tended to be low, and recorded sales cannot reveal purchases lost when shelves were empty. Retain the supplied safety stock and review the flagged items before ordering.

Follow `routine_usage.md` with refreshed files each week. The command can be scheduled on your computer with ChatGPT’s help setting it up; no schedule is installed. The calculation itself runs without ChatGPT.
