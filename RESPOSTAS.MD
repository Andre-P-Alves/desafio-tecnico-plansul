# Respostas — Desenvolvedor de Automação Júnior

---

## Parte 1 — Sobre o que você construiu

---

### 1.1 Descreva em até 5 linhas o que o seu pipeline faz, como se estivesse explicando para alguém da equipe de faturamento que não é técnico.

> O programa lê dois arquivos de cobrança, um arquivo vem do antigo sistema do convênio, e o outro da equipe interna, compara os dados e aponta diferenças. Depois renomeia os laudos PDF para um padrão com CPF e ID, e por fim gera uma planilha colorida com resumo e detalhes enviada por e-mail.

---

### 1.2 Qual foi a etapa mais difícil de implementar? O que tornou ela difícil e como você resolveu?

> Acredito que as partes que envolviam excel, não sou acostumado a lidar com nomes inconsistentes, matching de arquivos, ou fazer essas formatações coloridas. Mas uma pesquisa rápida foi o suficiente pra achar alguma biblioteca que resolvia esses problemas. Exemplo: https://medium.com/@aliakbarhosseinzadeh/data-cleaning-with-fuzzy-matching-in-python-fix-typos-names-and-more-5da6015016a4

---

### 1.3 A reconciliação entre o Excel e o CSV exigiu decisões sobre o que fazer quando os dados divergem. Descreva as principais decisões que você tomou:

- **Quando o valor de uma cobrança difere entre as fontes, qual prevalece e por quê?**

  > O valor vl_liquido do CSV, foi avisado no desafio que o CSV prevalece. Feita na função _detectar_divergencias do arquivo consolidar_cobranças.py

- **O que você faz com uma cobrança que está só no CSV e não tem correspondente no Excel?**

  > É incluída no relatório e marcada, destacada em laranja na planilha.

- **Como você identificou que dois registros se referem ao mesmo paciente mesmo com grafias diferentes?**

 > Algoritmo de pareamento Fuzz compara os nomes normalizados (sem acento, maiúsculo). O algoritmo tem um limiar, então é possível que em algum caso muito extremo, não capture o erro.

---

### 1.4 Como você fez o vínculo entre os arquivos PDF e os registros de cobrança? Descreva a lógica de similaridade que usou, qual foi o maior risco dessa abordagem e como você o mitigou.

> Para cada PDF, é removido do nome do arquivo as datas, erros e nomes de procedimentos, deixando só o candidato e nome do paciente. Compara com algoritmo Fuzz todos os pacientes do CSV. O principal risco seriam empates ou nomes muito curtos que matcham errado, isso depende claro do limiar mínimo, que foi de 65 e há descarte quando dois candidatos ficam a menos de 5 pontos um do outro.

---

### 1.5 Houve algum dado nos arquivos que te surpreendeu ou que você não esperava encontrar? Como você tratou?

> Particularmente não, claro que alguns dados tinham caracteres estranhos, ou estavam em uma formatação inconveniente, mas eventualmente esse tipo de coisa tem que ser tratada em alguma parte do código, porque sempre vai acabar aparecendo algum erro, seja de algum input humano ou proveniente de alguma outra, como por exemplo uma biblioteca sendo atualizada e mudando alguma coisa importante.

---

## Parte 2 — Sobre as decisões técnicas

---

### 2.1 Por que você escolheu a linguagem e as bibliotecas que usou? Quais alternativas considerou e por que descartou?

> Escolhi pela comodidade e praticidade, utilizo python faz tempo, é amplamente usada e possui grande disponibilidade de materiais.

---

### 2.2 Como você organizou o código? Explique brevemente a estrutura que criou e por que ela faz sentido para este problema.

> Separei cada desafio em um arquivo Python com nome relativo à solução feita, cada arquivo pode ser executado diretamente, ou usando os arquivos executáveis (que apenas executam o main.py). Há também o diretório de templates com o arquivo HTML enviado por e-mail. O certo era incluir o .env.template também, mas achei que ia apenas complicar na hora da execução. Os arquivos de código em python tem todas as funções necessárias para resolver o desafio, elas não são reutilizadas entre os códigos (que em um repositório seria o ideal ter um diretório para utilidades). A estrutura dos códigos é bem linear, começa com as funções básicas, utilizadas dentro de outras funções, e no final a main do arquivo. 

---

### 2.3 O pipeline lida com arquivos que podem chegar com problemas. Para cada cenário abaixo, descreva o que acontece no seu código:

- **O Excel chega com uma coluna faltando:**

  >  Sinaliza ValueError com a lista das colunas ausentes antes de processar os dados.

- **Uma linha do CSV tem o campo `vl_liquido` vazio ou com texto no lugar do valor:**

  > Usa a função _parse_brl, se falhar, converte com pd.to_numeric(errors="coerce"), onde o valor vira NaN e segue em frente, sem quebrar o pipeline.

- **Dois PDFs têm nomes tão parecidos que o algoritmo de similaridade empata:**

  > O arquivo PDF é pulado com status "pulado" e o "motivo" registra os dois candidatos e seus scores.

- **O pipeline roda duas vezes seguidas sem que os arquivos de entrada tenham mudado:**

  > Se os PDFs renomeados já existem no diretório de destino, ele é pulado com status "pulado" e o motivo "arquivo de destino já existe". O relatório é refeito normalmente.

---

### 2.4 Se o pipeline fosse rodar em produção todo mês com arquivos reais, o que você mudaria ou reforçaria em relação ao que entregou?

> Validação dos arquivos de entrada antes de processar (hash ou data de modificação para evitar reprocessar o mesmo arquivo), testes automatizados para as funções de normalização e detecção de divergência, e notificação de falha separada do e-mail de relatório (para saber quando o pipeline em si quebrou).

---

### 2.5 Tem alguma parte do código que você sabe que não está boa, mas deixou assim por limitação de tempo? O que está errado e como você corrigiria?

> Tem algumas melhorias que poderiam ser feitas, como incluir os caminhos dos diretórios no arquivo .env. Colocaria as funções simples e reutilizáveis dentro de um arquivo "utils" para facilitar importações no futuro, melhorando um pouco a escalabilidade do código. Poderia usar orientação a objetos também, mas depende muito de como é feito na empresa, então optei pela solução mais fácil e legível.

---

## Parte 3 — Visão de evolução

---

### 3.1 Hoje o pipeline é disparado manualmente via shell script. Se você fosse propor a próxima evolução de infraestrutura — considerando que a empresa usa servidores Linux (VPS) e não tem cloud — o que você sugeriria e por quê? Que problema concreto isso resolve que o cron não resolve?

> Algum programa pra admnistrar e executar tarefas (algo tipo rabbitMQ ou algo do tipo, só conheço esse) seria uma solução melhor, já que o shell script apenas executa todas as funções em ordem, então se alguma coisa interromper a execução, não é possível retomar de onde parou ou algo do tipo. Também não tenta novamente automaticamente e não guarda histórico de uso (mesmo que incluindo no log, se algo a mais falhar acaba nem anotando isso).

---

### 3.2 Imagine que o departamento passasse a receber um XML de retorno do convênio com o resultado de cada cobrança. Como você integraria essa nova fonte ao pipeline existente? O que mudaria no relatório final?

> Criaria uma função para processar que lê o XML com a biblioteca do python para XML, extrair as colunas desejadas. No arquivo consolidar_cobrancas.py, o merge ganharia uma terceira fonte de dados na hora de dar o join. O relatório ganharia coluna status_retorno e uma seção nova na página Resumo.

---

### 3.3 Se a empresa quisesse evoluir para um painel web simples onde o gestor pudesse consultar o histórico de relatórios e filtrar por mês, convênio ou tipo de alerta — como você estruturaria isso? Não precisa implementar, só descrever a abordagem técnica.

> Backend em FastAPI (python pra facilitar a integração com as funções criadas) e uma base de dados SQL armazenando cada execução e seus alertas. O relatório .xlsx ficaria em disco servido como download. Frontend simples em HTML/JS ou até mesmo Flask, com isso fica mais fácil fazer filtros por mês, convênio e tipo de divergência com alguma query.

---

### 3.4 Quais métricas ou condições você monitoraria se esse pipeline estivesse em produção? Dê exemplos concretos do que deveria disparar uma notificação imediata — e do que não deveria.

> Falha crítica que retorna 1, arquivos vazios ou corrompidos, porcentagem de divergência muito alta e falha no envio do e-mail.

---

## Parte 4 — Uso de agentes de IA

---

### 4.1 Você usou algum agente de IA para te ajudar a resolver o desafio? Se sim, para quais partes do processo você o utilizou e como?

> Sim, utilizei o Claude Code. Utilizei principalmente na questão 1 e 3, com o intuito de agilizar a programação, na questão 4 para gerar um template em HTML para o e-mail e na questão 5 para traduzir o arquivo .bat para um executável no shell do Linux (Não testei, uso Windows). Já conhecia a maioria das bibliotecas Python que eu gostaria de usar, pois já fiz um trabalho muito semelhante em experiências passadas, e como o desafio não possui nenhum código da empresa para usar como modelo, prefiro agilizar o processo de criação do zero com o agente de IA.

---

## Parte 5 — Contexto pessoal

---

### 5.1 Já trabalhou com automação de processos antes, mesmo que fora de um contexto profissional? Descreva brevemente o problema, o que você fez e qual foi o resultado.

> Sim, fiz um estágio curto de 3 meses na AAWZ partners onde fiz automações semelhantes à esse teste técnico, minha função era agilizar a coleta de dados para o setor financeiro, durante o estágio, fiz tarefas que coincidem com o que foi pedido no teste.

---

### 5.2 O que você faria diferente se tivesse o dobro do tempo para resolver este desafio?

> Acredito que solucionaria as questões da pergunta 2.5. Como é um desafio técnico, acho que não tem muito o que explorar além da resoluçõa.

---

### 5.3 Teve alguma parte do desafio que você achou mal especificada ou ambígua? O que estava faltando e como você lidou com a ambiguidade?

> Não, achei bem explicado.
