# accounts/migrations/0002_add_schoolclass_studentprofile.py
#
# The accounts_schoolclass and accounts_studentprofile tables were defined in
# 0001_initial but that migration was fake-applied (the DB was created from the
# old `app` schema which had no such tables).  This migration creates them for
# real.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SchoolClass',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(
                    help_text='Human-readable class name, e.g. "4.B – 2026".',
                    max_length=100,
                    unique=True,
                )),
                ('school_year', models.CharField(
                    blank=True,
                    help_text='Optional school year label, e.g. "2025/2026".',
                    max_length=20,
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('teacher', models.ForeignKey(
                    blank=True,
                    help_text='The teacher/treasurer responsible for this class.',
                    limit_choices_to={'is_treasurer': True},
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='managed_classes',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'School Class',
                'verbose_name_plural': 'School Classes',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='StudentProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('child_name', models.CharField(
                    help_text='Full name of the child (displayed on treasurer dashboards).',
                    max_length=200,
                )),
                ('variable_symbol', models.CharField(
                    help_text="Unique up-to-10-digit code used to identify this student's bank transfers.",
                    max_length=10,
                    unique=True,
                    verbose_name='Variable Symbol (VS)',
                )),
                ('is_active', models.BooleanField(
                    default=True,
                    help_text='Uncheck to exclude this student from new payment requests.',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('parent', models.ForeignKey(
                    help_text='The parent/guardian who will receive payment requests and pay.',
                    limit_choices_to={'is_treasurer': False},
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='children',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('school_class', models.ForeignKey(
                    help_text='The class this student belongs to.',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='students',
                    to='accounts.schoolclass',
                )),
            ],
            options={
                'verbose_name': 'Student Profile',
                'verbose_name_plural': 'Student Profiles',
                'ordering': ['school_class', 'child_name'],
            },
        ),
    ]
