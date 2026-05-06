import hmac
import hashlib
import sys

# IMPORTANTE: Esta chave DEVE ser a mesma que está no main.py
LICENCA_SECRET_KEY = "orcamentos-saas-secret-2026-xyz"

def gerar_chave(cnpj: str):
    # Limpa o CNPJ (deixa apenas números)
    cnpj_limpo = "".join(c for c in cnpj if c.isdigit())
    
    if not cnpj_limpo:
        print("Erro: CNPJ inválido ou vazio.")
        return

    # Gera o HMAC-SHA256 do CNPJ usando a nossa Secret Key
    chave = hmac.new(
        LICENCA_SECRET_KEY.encode(),
        cnpj_limpo.encode(),
        hashlib.sha256
    ).hexdigest()
    
    print("-" * 50)
    print(f"GERADOR DE LICENÇAS - SISTEMA DE ORÇAMENTOS")
    print("-" * 50)
    print(f"Empresa (CNPJ): {cnpj}")
    print(f"Chave de Ativação: {chave}")
    print("-" * 50)
    print("\nInstruções: Forneça esta chave ao cliente para ativação no painel.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        gerar_chave(sys.argv[1])
    else:
        cnpj_input = input("Digite o CNPJ para gerar a licença: ")
        gerar_chave(cnpj_input)
