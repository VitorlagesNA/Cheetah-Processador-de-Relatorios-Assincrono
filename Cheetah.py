import time
import uuid
import json
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import fakeredis

app = FastAPI(
    title="Cheetah - Asynchronous Report Processor",
    description="API de processamento assíncrono de relatórios em segundo plano com acompanhamento de status.",
    version="1.0.0"
)

# Cliente Redis simulado em memória
redis_client = fakeredis.FakeStrictRedis(decode_responses=True)


# Modelo de dados para a requisição de criação de relatório
class SolicitacaoRelatorio(BaseModel):
    titulo: str
    linhas_dados: int = 500  # Quantidade simulada de dados a processar


# --- FUNÇÃO DE PROCESSAMENTO EM SEGUNDO PLANO (WORKER SIMULADO) ---

def processar_relatorio_background(task_id: str, titulo: str, total_linhas: int):
    """
    Função pesada executada em segundo plano.
    Simula o processamento longo e atualiza o estado no Redis.
    """
    key = f"cheetah:task:{task_id}"

    # 1. Atualiza status para PROCESSING
    dados_task = {
        "task_id": task_id,
        "titulo": titulo,
        "status": "PROCESSING",
        "progresso": "0%",
        "resultado": None
    }
    redis_client.set(key, json.dumps(dados_task))

    # Simulação do processamento pesado (ex: 5 segundos de execução)
    time.sleep(3)
    dados_task["progresso"] = "50%"
    redis_client.set(key, json.dumps(dados_task))

    time.sleep(3)  # Simula a finalização da geração do PDF/CSV

    # 2. Atualiza status para COMPLETED e gera link de download fictício
    dados_task["status"] = "COMPLETED"
    dados_task["progresso"] = "100%"
    dados_task["resultado"] = f"/downloads/relatorio_{task_id}.pdf"
    
    # Guarda o resultado no Redis com tempo de expiração de 1 hora (3600 segundos)
    redis_client.setex(key, 3600, json.dumps(dados_task))


# --- ROTAS DA API CHEETAH ---

@app.get("/")
async def root():
    return {
        "sistema": "Cheetah Async Processor",
        "status": "Operacional",
        "documentacao": "/docs"
    }


@app.post("/relatorios", status_code=202)
async def criar_relatorio(solicitacao: SolicitacaoRelatorio, background_tasks: BackgroundTasks):
    """
    Recebe o pedido, gera o ID único e responde INSTANTANEAMENTE (HTTP 202 Accepted),
    enquanto o processamento acontece em segundo plano.
    """
    task_id = str(uuid.uuid4())
    key = f"cheetah:task:{task_id}"

    # Registo inicial no Redis (PENDING)
    dados_iniciais = {
        "task_id": task_id,
        "titulo": solicitacao.titulo,
        "status": "PENDING",
        "progresso": "0%",
        "resultado": None
    }
    redis_client.set(key, json.dumps(dados_iniciais))

    # Dispara a função pesada para rodar em segundo plano
    background_tasks.add_task(
        processar_relatorio_background, 
        task_id, 
        solicitacao.titulo, 
        solicitacao.linhas_dados
    )

    # Resposta rápida enviada ao cliente em milissegundos
    return {
        "mensagem": "Solicitação recebida com sucesso. Processamento iniciado em segundo plano.",
        "task_id": task_id,
        "status": "PENDING",
        "consultar_status": f"/relatorios/{task_id}"
    }


@app.get("/relatorios/{task_id}")
async def obter_status_relatorio(task_id: str):
    """
    Permite ao cliente consultar o progresso do processamento pelo task_id.
    """
    key = f"cheetah:task:{task_id}"
    dados_raw = redis_client.get(key)

    if not dados_raw:
        raise HTTPException(
            status_code=404, 
            detail="Tarefa não encontrada ou expirada."
        )

    return json.loads(dados_raw)