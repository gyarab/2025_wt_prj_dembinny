"""
Migration: add plain_password to ImportRow.

Stores the plain-text initial password for newly created accounts so that
credentials can be exported to a handout sheet for the teacher.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('importer', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='importrow',
            name='plain_password',
            field=models.CharField(
                blank=True,
                default='',
                max_length=128,
                verbose_name='Initial password',
                help_text=(
                    'Plain-text password set at import time '
                    '(empty for pre-existing accounts).'
                ),
            ),
            preserve_default=False,
        ),
    ]
