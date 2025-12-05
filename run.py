from app import create_app

app = create_app()

if __name__ == '__main__':
    print("Starting Commission Processor...")
    print("Open http://localhost:5000 in your browser")
    app.run(debug=True, port=5000)
