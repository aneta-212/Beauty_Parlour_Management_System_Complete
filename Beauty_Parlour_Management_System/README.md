# Beauty Parlour Management System — complete feature update

## Upgrade safely (keep your existing accounts and bookings)

This ZIP contains application code, migrations and sample service images. It deliberately contains NO db.sqlite3, existing customer uploads, passwords or virtual environment.

1. Stop your current server with Ctrl+C.
2. Make a copy of your existing project folder as a backup, especially db.sqlite3 and media.
3. Extract the new ZIP separately. Open its Beauty_Parlour_Management_System folder (the one containing manage.py).
4. Copy its contents into your existing project folder containing manage.py. Replace matching code files. Keep your existing db.sqlite3, your .venv and all uploaded media. When merging media folders, keep your own images if you replaced the sample images.
5. Double-click SETUP_WINDOWS.bat. It installs requirements, applies the migrations and adds missing sample services/demo beauticians.
6. Double-click START_WINDOWS.bat. Sign in using your existing account.

The new migrations preserve records and add features. Historical single-service appointments receive treatment snapshots. Older bookings without a beautician can be assigned from Dashboard → Assign staff / reschedule. Past unassigned requests can be closed by the manager. Do not delete db.sqlite3 to fix a migration error; send the error for diagnosis.

## New installation

Python 3.10+ and the Windows `py` launcher are required. The project uses Django 5.2 and Pillow.

1. Extract the ZIP and open the folder containing manage.py.
2. Double-click SETUP_WINDOWS.bat.
3. Double-click CREATE_ADMIN_WINDOWS.bat and choose your own admin login. Password characters are not displayed as you type.
4. Double-click START_WINDOWS.bat and open http://127.0.0.1:8000/ . Keep the terminal open. Ctrl+C stops the server.

For PyCharm, open this same folder and choose .venv\Scripts\python.exe as the interpreter after setup. The batch files use their own directory, avoiding the outer-folder problem.

Manual setup commands, run one at a time in the folder containing manage.py:

```bat
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_services
.\.venv\Scripts\python.exe manage.py seed_staff
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

## Roles

- Customer: edit their profile; book services/packages; reschedule/cancel under the notice policy; view their own bills, notifications and waiting-list requests; review their completed appointments.
- Beautician: manager creates a login from Staff → Create beautician login. Linked beauticians see only their assigned appointment details and calendar. They do not manage money, inventory or other customers. Inactive staff lose schedule access.
- Manager: a Django user marked Staff status, without a linked beautician record, can manage reception, scheduling, services, reports, payments, stock and settings. A linked beautician remains restricted even if Staff status is accidentally enabled.
- Superuser: full manager access plus private database/media backup download and Django account administration. A superuser remains a manager even if linked to a staff record.

Demo beauticians are scheduling records only. No demo login/password is shipped. Rename them and set their real skills and hours before use. Manage manager login permissions in Django Admin. Use the custom management pages for bookings and money; these records are read-only in Django Admin.

## Booking, packages and reception

Choose a primary service with optional additional services, OR a package. A package replaces individual selections. All chosen treatments use ONE qualified beautician in one continuous appointment. Duration is the sum of all selected treatments; packages subtract their fixed discount. Start times use 15-minute intervals, while reservations cover every treatment minute.

Availability checks staff skills, working days/hours, leave, breaks, salon closures, opening hours, booking horizon, existing appointments and the customer's own overlapping bookings. Pending and approved appointments reserve time. The server rechecks submitted slots in a transaction; database uniqueness prevents simultaneous staff reservations at the same minute.

Rescheduling retains service snapshots, duration and quoted price, even if prices change or a booked package is later disabled. Customers' changes return to Pending; managers' reception changes are approved immediately. Managers can assign staff or reschedule upcoming active bookings from Dashboard. Cancellation releases reservations. Settings controls how many hours' notice customers must give. Completed/rejected/cancelled/no-show bookings cannot be reopened through the interface.

Walk-in means a booking entered by reception without requiring an account. Select the next available time; backdated appointments are not supported. Search an existing customer and choose Book for this customer to link their booking. Without an account, the record stays visible to reception but cannot receive in-app notifications, password reset or account email reminders.

The day/week calendar can filter by beautician. Managers see all schedules; beauticians only their own. Mark an approved appointment as No-show only after it starts, or Completed after its scheduled end. Appointment lists show the latest 100 matching records; calendars use the selected day/week. Customer search covers account names/emails/phones and recent guest booking names/phones.

## Waiting list and reviews

A customer can join for a service and date. Managers use Waiting list to offer a currently available time. An offer creates a notification and queued email; it does not hold a slot. The customer must finish booking while availability remains. A matching completed booking request updates the waitlist to Booked. Customers can withdraw requests; managers can close them.

Only the owning customer can create/update a review for a completed appointment. Public reviews show treatment, rating, date and comment, not customer names/contact details. Superusers can hide an inappropriate review using Django Admin's Visible checkbox.

## Bills, payments, corrections and refunds

After completion, create one bill per appointment, with an optional additional discount that cannot exceed the booked quote. The bill snapshots treatment names and amount. Print / save PDF uses the browser's print dialog.

Record cash/UPI/card money already received; this is NOT an online payment gateway. Partial payments are supported and overpayments are blocked. Repeated submission of the same payment form is idempotent; a fresh form creates a separate transaction.

Payment corrections and refunds never erase the original record:
- Correction reverses a mistaken recorded amount, reopening that amount of unpaid balance. To change a payment method, correct the original amount with a reason and record the replacement payment with the correct method.
- Refund records money already returned and adds a matching credit to the bill, reducing both the net paid amount and the payable total. It does not automatically initiate a bank/UPI refund.

Both require a reason and cannot exceed the remaining unadjusted payment amount. Adjustments appear on the bill and in activity history. The site does not calculate GST, process tax invoices or model accounting profit.

## Reports, stock and salon settings

Reports accept a month and show recorded payments, corrections/refunds, net receipts, payment methods, daily totals, appointment statuses and a bar chart of popular completed treatments. Current unpaid bills are across all dates and labelled separately. CSV exports payment/adjustment rows; Print / save PDF exports the report visually. Receipt dates and appointment dates are different and labelled. These reports are records, not bank reconciliation.

Inventory holds products, units and low-stock thresholds. Products start at zero; Receive / use records positive deliveries or negative consumption/corrections with reasons. Negative stock is blocked. Stock movements are logged and cannot be deleted through the interface. Stock usage is entered manually, not deducted automatically when services finish.

Settings edits the salon name, contact details, address, weekday/Sunday opening hours, booking horizon (1–730 days) and customer change-notice hours. Staff hours are intersected with salon hours. Breaks/holidays are dated time blocks, for one beautician or the whole salon. All-day closures can use 00:00–23:59. Recurring breaks are not included; add dated entries. Existing overlapping active appointments must be resolved before inserting a block. Upcoming active appointments must be resolved before staff working hours/skills or salon opening hours are changed.

The shared header/footer and booking page use salon settings. The original About, Home, Gallery and Contact promotional content may contain sample claims or contact text; edit those templates to match your parlour before real use.

## Notifications and password reset

In-app updates appear immediately when bookings, statuses, bills, payments and refunds change. Customers can mark only their own updates as read. Email notifications use a queue. Password reset uses Django's expiring single-use reset links.

By default emails are PRINTED TO THE SERVER TERMINAL for local testing; they are not delivered to an inbox. SMTP credentials and a public site URL are needed for real delivery. Read EMAIL_SETUP.md. No email account is connected by this ZIP.

PROCESS_REMINDERS_WINDOWS.bat queues reminders for approved account appointments within 24 hours and processes notification emails. Run it manually for a demo. RUN_NOTIFICATION_WORKER.bat has no pause and can be scheduled hourly with Windows Task Scheduler for automatic delivery while the computer is on. Do not run multiple workers concurrently. A rare worker crash after email delivery but before marking sent can result in a repeated email on retry.

## Backup and restore

Superuser → Backup downloads a consistent SQLite snapshot plus uploaded media. BACKUP_WINDOWS.bat creates a ZIP in the local backups folder. Copy private backups to a separate safe location; they include customer information and account password hashes.

To restore: STOP the server and notification worker, then run:

```bat
.\.venv\Scripts\python.exe manage.py restore_parlour "C:\path\backup.zip" --confirm-restore
.\.venv\Scripts\python.exe manage.py migrate
```

Restore accepts trusted archives made by this project, validates archive paths and database integrity, and creates a before_restore recovery ZIP before replacing database/media. Restore replaces current records: changes made after the backup will be lost. The restore limit is 1 GiB uncompressed. This utility targets local SQLite; it is not a PostgreSQL or cloud backup service.

## Validation and deployment scope

Run ` .venv\Scripts\python.exe manage.py test salon ` to check workflows. Tests cover old features plus profile uniqueness, password reset, multi-service duration/price, packages, permissions, notice rules, breaks, reception bookings, waitlist offers, reviews, financial adjustments, stock limits, reports/CSV safety, notifications/reminders, CSRF and backup/restore validation.

This is a local-development project with DEBUG enabled. Configure secrets, allowed hosts, HTTPS, email, rate limiting, production media/static serving and routine backups before public deployment. SQLite concurrency is appropriate for a small local project and has not been load-tested for high traffic. Styling/CDN libraries, some original promotional images and maps need internet access.

Browser visual QA and Windows batch execution were not available in this environment. Automated Django route/template and workflow checks were performed. See FEATURE_CHECKLIST.md for the full feature list.

Final automated validation: 44 tests passed. Django system checks and migration consistency checks passed. Inline booking JavaScript passed a syntax check. Browser visual testing and Windows execution remain unverified.
