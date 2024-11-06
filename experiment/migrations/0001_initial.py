# Generated by Django 5.1.2 on 2024-11-05 16:39

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
                ("email", models.EmailField(blank=True, max_length=254, null=True)),
                ("agreed_to_terms", models.BooleanField(default=False)),
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
                ("name", models.CharField(max_length=100)),
                ("audio_file", models.FileField(upload_to="rhythms/")),
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
                ("complexity_level", models.CharField(default="simple", max_length=50)),
                ("ear_order", models.CharField(default="left_first", max_length=50)),
                (
                    "participant",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="experiment.participant",
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
                (
                    "ear_first_order",
                    models.CharField(default="left_first", max_length=50),
                ),
                ("is_practice", models.BooleanField(default=False)),
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
                ("response", models.TextField(blank=True, null=True)),
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
