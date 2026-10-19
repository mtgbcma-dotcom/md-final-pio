from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from social.models import User, Post

PEOPLE = [
    ('clara_design', 'Clara Martins', 'Design, café e um olhar curioso para as pequenas coisas.', [
        'Um lembrete para hoje: nem toda ideia precisa nascer pronta. Às vezes, um rascunho e uma boa conversa já são um ótimo começo. 🌱',
        'Qual detalhe de um aplicativo faz você pensar “alguém realmente pensou em mim”? Para mim, é uma mensagem de erro que ajuda de verdade.',
        'Troquei meia hora de rolagem infinita por uma caminhada sem fones. Voltei com mais ideias do que esperava.']),
    ('rafa_codigo', 'Rafael Oliveira', 'Transformando café em Python. Aprendendo um pouco todos os dias.', [
        'A melhor parte de terminar um projeto é perceber o quanto você aprendeu nos erros que agora sabe resolver. Um commit de cada vez. 🧩',
        'Pequena vitória do dia: escrevi um teste que encontrou um erro antes de alguém encontrar em produção. Vale comemorar, sim!',
        'Dica de quem já esqueceu: documente como rodar seu projeto enquanto tudo ainda está fresco na memória. Seu eu do futuro agradece.']),
    ('bia_leituras', 'Beatriz Santos', 'Livros, cidades e conversas que fazem pensar diferente.', [
        'Terminei um livro e agora quero conversar com todo mundo sobre ele. Qual foi a última leitura que ficou com vocês por dias? 📚',
        'Tem conversa que funciona como janela aberta: entra um pouco de ar e a gente passa a enxergar o mesmo lugar de outro jeito.',
        'Domingo combina com café demorado, páginas marcadas e uma lista de ideias que talvez nem saiam do papel. E está tudo bem.']),
    ('leo_fotografia', 'Leonardo Lima', 'Fotografando o cotidiano. Sempre em busca de uma boa luz.', [
        'A luz das cinco da tarde transforma até o caminho de sempre. Hoje eu parei para olhar. Recomendo. ☀️',
        'Fazer algo devagar também é uma escolha criativa. Hoje foi dia de observar antes de apertar o botão.',
        'Uma pergunta para a sua próxima caminhada: o que você sempre passa perto, mas nunca reparou?']),
]

class Command(BaseCommand):
    help = 'Cria 4 perfis fictícios e 12 publicações. As contas demonstrativas não permitem login.'

    @transaction.atomic
    def handle(self, *args, **options):
        created = 0
        now = timezone.now()
        for index, (username, name, bio, posts) in enumerate(PEOPLE):
            user, new = User.objects.get_or_create(username=username, defaults={
                'name': name, 'email': f'{username}@example.invalid', 'bio': bio,
            })
            if new:
                user.set_unusable_password()
                user.save(update_fields=['password'])
            for offset, text in enumerate(posts):
                post, new_post = Post.objects.get_or_create(author=user, content=text)
                if new_post:
                    Post.objects.filter(pk=post.pk).update(created_at=now - timedelta(hours=offset * 5 + index, minutes=index * 13))
                    created += 1
        self.stdout.write(self.style.SUCCESS(f'Demonstração pronta: {created} novas publicações. Crie sua própria conta e siga os perfis em Explorar.'))
