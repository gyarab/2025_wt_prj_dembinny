# finances/migrations/0002_add_school_class_to_bankaccount.py
#
# finances_bankaccount was created by the old `app` schema without the
# school_class FK.  finances.0001_initial was fake-applied, so the column
# was never added.  This migration adds it for real.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_schoolclass_studentprofile'),
        ('finances', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='bankaccount',
            name='school_class',
            field=models.OneToOneField(
                blank=True,
                help_text='The class this bank account belongs to.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='bank_account',
                to='accounts.schoolclass',
            ),
        ),
    ]
