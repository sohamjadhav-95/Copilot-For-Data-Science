# run.py — Entry point for Data Science Copilot
from app import create_app

app = create_app()

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("  🧪 Data Science Copilot — Starting...")
    print("  Open http://localhost:5000 in your browser")
    print("=" * 60 + "\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
