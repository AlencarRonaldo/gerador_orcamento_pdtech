import sqlite3

def check():
    try:
        conn = sqlite3.connect('orcamentos.db')
        cursor = conn.cursor()
        
        print("--- CONFIG EMPRESA ---")
        cursor.execute("SELECT id, empresa_nome, login_email FROM config_empresa")
        configs = cursor.fetchall()
        for cfg in configs:
            print(f"ID: {cfg[0]} | Nome: {cfg[1]} | Email: {cfg[2]}")

        print("\n--- CATALOGO ---")
        cursor.execute("SELECT id, descricao, categoria FROM catalogo_itens")
        itens = cursor.fetchall()
        for i in itens:
            print(f"ID: {i[0]} | Desc: {i[1]} | Cat: {i[2]}")
        
        print("\n--- CLIENTES ---")
        cursor.execute("SELECT id, nome FROM clientes")
        clientes = cursor.fetchall()
        for c in clientes:
            print(f"ID: {c[0]} | Nome: {c[1]}")
            
        conn.close()
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    check()
