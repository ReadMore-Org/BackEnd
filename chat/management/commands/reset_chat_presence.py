from django.core.management.base import BaseCommand

from chat.models import UserPresence


class Command(BaseCommand):
    help = "Zera os contadores de presença (use depois de um encerramento abrupto do servidor)."

    def handle(self, *args, **options):
        total = UserPresence.objects.filter(connections__gt=0).update(connections=0)
        self.stdout.write(self.style.SUCCESS(f"{total} presença(s) zerada(s)."))
