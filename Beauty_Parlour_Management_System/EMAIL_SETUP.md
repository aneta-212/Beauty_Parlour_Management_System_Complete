# Email delivery and reminder setup

The default backend prints email text and reset links in the terminal. This is useful for demonstrating password reset without sending real messages.

For actual delivery, obtain SMTP settings from your email provider. Do not put a password in source code or commit it to a repository. On Windows Command Prompt, set environment variables before starting the server or worker:

```bat
set EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
set EMAIL_HOST=your-smtp-host
set EMAIL_PORT=587
set EMAIL_HOST_USER=your-email-address
set EMAIL_HOST_PASSWORD=your-provider-app-password
set EMAIL_USE_TLS=true
set DEFAULT_FROM_EMAIL=your-email-address
set SITE_URL=https://your-deployed-site.example
START_WINDOWS.bat
```

These example values must be replaced. Use your provider's supported TLS/port settings. The provided configuration supports STARTTLS (commonly port 587). No credentials are provided and no test message was sent to a real person.

For a local demonstration, leave the default console backend and SITE_URL. Submit Forgot password, then copy the reset link from the server console into your browser. Unknown email addresses show the same response but produce no reset email.

For notifications:

```bat
.venv\Scripts\python.exe manage.py send_reminders
.venv\Scripts\python.exe manage.py send_notifications
```

The first command queues reminders for approved account bookings in the next 24 hours. The second sends up to 200 pending emails. New in-app notifications do not depend on email delivery. If a send fails, its notification remains pending. Rescheduling clears the reminder flag so a new reminder can be queued for the new time.

For hourly automatic processing, create a Windows Task Scheduler task that runs RUN_NOTIFICATION_WORKER.bat from the project folder and repeats every hour. Ensure the task's account/environment has the same SMTP variables. The computer must be running. Use a single worker; the app does not install a scheduled task automatically. Password-reset email is sent by the web request and does not need this worker.

Console-email messages are marked processed as a development simulation. For a real deployment, configure SMTP before creating live notifications.
