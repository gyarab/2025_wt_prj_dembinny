# app/migrations/0001_squashed.py
#
# This is a stub migration. The `app` models have been moved to dedicated apps:
#   - accounts  (CustomUser, SchoolClass, StudentProfile)
#   - finances  (BankAccount, PaymentRequest, Transaction, Expense)
#   - communications (NotificationLog)
#
# No database tables are created here; the real tables are owned by those apps.
# This stub exists so Django's migration graph is consistent and the app can
# be removed cleanly in a future commit once all code references are updated.

from django.db import migrations


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('accounts',       '0001_initial'),
        ('finances',       '0001_initial'),
        ('communications', '0001_initial'),
    ]

    operations = []  # nothing to do — all tables live in the new apps
