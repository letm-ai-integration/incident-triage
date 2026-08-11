from app.llm.client import get_chat_model


def main():
    print("Creating OpenRouter client...")

    llm = get_chat_model()

    print("Client created successfully.")
    print("Sending test request...")

    response = llm.invoke(
        "Reply with exactly: OPENROUTER_OK"
    )

    print("Response received:")
    print(response.content)

    print("\nOPENROUTER TEST PASSED")


if __name__ == "__main__":
    main()