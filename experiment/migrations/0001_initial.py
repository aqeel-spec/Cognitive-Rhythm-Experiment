# Generated by Django 5.1.2 on 2024-11-06 19:32

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Participant",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("age", models.IntegerField()),
                ("is_right_handed", models.BooleanField(default=True)),
                ("has_music_background", models.BooleanField(default=False)),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, null=True, unique=True
                    ),
                ),
                ("agreed_to_terms", models.BooleanField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="RhythmSequence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, unique=True)),
                (
                    "rhythm_type",
                    models.CharField(
                        choices=[("simple", "Simple"), ("complex", "Complex")],
                        default="simple",
                        max_length=10,
                    ),
                ),
                (
                    "sequence_data",
                    models.JSONField(
                        help_text="Enter the rhythm sequence in JSON format"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ExperimentSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("start_time", models.DateTimeField(auto_now_add=True)),
                ("end_time", models.DateTimeField(blank=True, null=True)),
                (
                    "complexity_level",
                    models.CharField(
                        choices=[("simple", "Simple"), ("complex", "Complex")],
                        default="simple",
                        max_length=50,
                    ),
                ),
                (
                    "ear_order",
                    models.CharField(
                        choices=[
                            ("left_first", "Left First"),
                            ("right_first", "Right First"),
                        ],
                        default="left_first",
                        max_length=50,
                    ),
                ),
                (
                    "first_ear",
                    models.CharField(
                        choices=[("left", "Left"), ("right", "Right")],
                        default="left",
                        max_length=5,
                    ),
                ),
                (
                    "session_config",
                    models.JSONField(
                        blank=True,
                        help_text="Session-specific configuration data",
                        null=True,
                    ),
                ),
                (
                    "participant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="experiment.participant",
                    ),
                ),
                (
                    "first_rhythm_sequence",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="first_session_rhythm",
                        to="experiment.rhythmsequence",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Trial",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("trial_number", models.IntegerField()),
                ("is_practice", models.BooleanField(default=False)),
                ("sequence_order", models.IntegerField(default=1)),
                (
                    "tap_accuracy_score",
                    models.DecimalField(
                        blank=True, decimal_places=2, max_digits=5, null=True
                    ),
                ),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="experiment.participant",
                    ),
                ),
                (
                    "rhythm_sequence",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="experiment.rhythmsequence",
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="experiment.experimentsession",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TapRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("tap_times", models.JSONField(help_text="List of tap timestamps")),
                (
                    "average_reaction_time",
                    models.DurationField(
                        blank=True, help_text="Average reaction time per tap", null=True
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "participant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="experiment.participant",
                    ),
                ),
                (
                    "trial",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="tap_records",
                        to="experiment.trial",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Analysis",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("reaction_time", models.DurationField(blank=True, null=True)),
                (
                    "response_data",
                    models.JSONField(
                        blank=True,
                        help_text="Structured response data in JSON format",
                        null=True,
                    ),
                ),
                (
                    "trial",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="experiment.trial",
                    ),
                ),
            ],
        ),
    ]
