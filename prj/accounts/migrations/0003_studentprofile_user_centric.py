# accounts/migrations/0003_studentprofile_user_centric.py
#
# Architecture change: StudentProfile becomes a thin enrollment record.
#
# Changes:
#   1. Add `user` OneToOneField to CustomUser (the student themselves)
#   2. Remove `child_name` CharField
#   3. Make `parent` nullable (SET_NULL instead of CASCADE NOT NULL)
#   4. Make `school_class` nullable (SET_NULL instead of CASCADE NOT NULL)
#   5. Update Meta.ordering to use user__last_name instead of child_name

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_add_schoolclass_studentprofile'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1a. Add `user` as nullable first so existing rows can be populated.
        migrations.AddField(
            model_name='studentprofile',
            name='user',
            field=models.OneToOneField(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='student_profile',
                to=settings.AUTH_USER_MODEL,
                help_text="The student's own user account.",
            ),
        ),

        # 1b. Populate user_id from parent_id for existing rows
        #     (best-effort: in a fresh dev DB the parent user IS effectively
        #      the placeholder; replace with the real student user if needed).
        migrations.RunSQL(
            sql="UPDATE accounts_studentprofile SET user_id = parent_id WHERE user_id IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),

        # 1c. Now make `user` non-nullable.
        migrations.AlterField(
            model_name='studentprofile',
            name='user',
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='student_profile',
                to=settings.AUTH_USER_MODEL,
                help_text="The student's own user account.",
            ),
        ),

        # 2. Remove `child_name`.
        migrations.RemoveField(
            model_name='studentprofile',
            name='child_name',
        ),

        # 3. Make `parent` nullable with SET_NULL.
        migrations.AlterField(
            model_name='studentprofile',
            name='parent',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='children',
                to=settings.AUTH_USER_MODEL,
                help_text='Optional parent/guardian linked to this student.',
            ),
        ),

        # 4. Make `school_class` nullable with SET_NULL.
        migrations.AlterField(
            model_name='studentprofile',
            name='school_class',
            field=models.ForeignKey(
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='students',
                to='accounts.schoolclass',
                help_text='The class this student belongs to.',
            ),
        ),

        # 5. Update Meta ordering.
        migrations.AlterModelOptions(
            name='studentprofile',
            options={
                'ordering': ['school_class', 'user__last_name', 'user__first_name'],
                'verbose_name': 'Student Profile',
                'verbose_name_plural': 'Student Profiles',
            },
        ),
    ]
