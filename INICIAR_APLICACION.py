"""
INICIAR APLICACION - Pipeline InSAR
Ejecute este archivo para abrir la interfaz web del pipeline.
"""
import subprocess, sys, os, webbrowser, time

def install_flask():
    print("Instalando Flask (primera vez)...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "flask", "-q"])
    print("[OK] Flask instalado.")

def main():
    # Verificar Flask
    try:
        import flask
    except ImportError:
        install_flask()
    
    script_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Scripts")
    server = os.path.join(script_dir, "servidor_web.py")
    
    if not os.path.exists(server):
        print(f"ERROR: No se encontro {server}")
        input("Presione Enter para salir...")
        return
    
    print("=" * 50)
    print("  PIPELINE InSAR - Iniciando Interfaz Web...")
    print("  Se abrira su navegador automaticamente.")
    print("  Para detener, cierre esta ventana.")
    print("=" * 50)
    
    # Abrir navegador despues de 2 segundos
    def open_browser():
        time.sleep(2)
        webbrowser.open("http://localhost:5000")
    
    import threading
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Iniciar servidor
    subprocess.run([sys.executable, server], cwd=script_dir)

if __name__ == "__main__":
    main()
