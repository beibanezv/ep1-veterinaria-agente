"""Interfaz intercambiable de LLM (D1): ClienteGroq por defecto, ClienteFalso para dev/tests sin cuota."""
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

MODELO_DEFECTO = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
MODELO_RAPIDO = os.getenv("GROQ_MODEL_FAST", "openai/gpt-oss-20b")


@dataclass
class RespuestaLLM:
    texto: str
    modelo: str
    tokens_entrada: int = 0
    tokens_salida: int = 0


class ClienteLLM:
    def completar(self, sistema: str, usuario: str) -> RespuestaLLM:
        raise NotImplementedError


class ClienteGroq(ClienteLLM):
    """Groq via SDK crudo; reasoning_effort='low' (convencion del curso para gpt-oss)."""

    def __init__(self, modelo: str = "", usar_modelo_rapido: bool = False):
        self.modelo = modelo or (MODELO_RAPIDO if usar_modelo_rapido else MODELO_DEFECTO)
        self._cliente = None

    def _obtener_cliente(self):
        if self._cliente is None:
            from groq import Groq

            self._cliente = Groq()
        return self._cliente

    def completar(self, sistema: str, usuario: str) -> RespuestaLLM:
        r = self._obtener_cliente().chat.completions.create(
            model=self.modelo,
            messages=[
                {"role": "system", "content": sistema},
                {"role": "user", "content": usuario},
            ],
            temperature=0.2,
            max_completion_tokens=1024,
            reasoning_effort="low",
        )
        uso = getattr(r, "usage", None)
        return RespuestaLLM(
            texto=r.choices[0].message.content.strip(),
            modelo=self.modelo,
            tokens_entrada=uso.prompt_tokens if uso else 0,
            tokens_salida=uso.completion_tokens if uso else 0,
        )


class ClienteFalso(ClienteLLM):
    """Determinista: cita los fragmentos [F#] y herramientas [T#] del prompt. Sin red, sin cuota."""

    def __init__(self, modelo: str = "cliente-falso"):
        self.modelo = modelo

    def completar(self, sistema: str, usuario: str) -> RespuestaLLM:
        marcadores = re.findall(r"\[(?:F|T)\d+\]", usuario)
        unicos = sorted(set(marcadores), key=lambda m: (m[1], int(m[2:-1])))
        if unicos:
            texto = (
                "(respuesta simulada) Recomendacion clinica formulada a partir del contexto recuperado: "
                f"aplica la indicacion descrita en {unicos[0]}. {' '.join(unicos)}"
            )
        else:
            texto = "(respuesta simulada) No tengo informacion suficiente en la base de conocimiento interna."
        return RespuestaLLM(texto=texto, modelo=self.modelo)


class ClienteLangChain(ClienteLLM):
    """Mismo contrato, via langchain-groq (lazy import; tracing LangSmith si hay key)."""

    def __init__(self, modelo: str = "", usar_modelo_rapido: bool = False):
        self.modelo = modelo or (MODELO_RAPIDO if usar_modelo_rapido else MODELO_DEFECTO)

    def completar(self, sistema: str, usuario: str) -> RespuestaLLM:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_groq import ChatGroq

        try:
            from agent.observabilidad import init_langsmith
            init_langsmith()
        except ImportError:
            pass
        chat = ChatGroq(model=self.modelo, temperature=0.2, max_tokens=1024)
        r = chat.invoke([SystemMessage(content=sistema), HumanMessage(content=usuario)])
        return RespuestaLLM(texto=str(r.content).strip(), modelo=self.modelo)
