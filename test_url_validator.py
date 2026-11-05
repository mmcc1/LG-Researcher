from security.url_validator import (
    UnsafeUrlError,
    UrlValidator,
)


validator = UrlValidator()


urls = [
    "https://bitcoin.org/",
    "https://example.com/",
    "http://localhost:11434/",
    "http://127.0.0.1:11434/",
    "http://192.168.1.1/",
    "http://10.0.0.1/",
    "file:///etc/passwd",
]


for url in urls:

    print()
    print(url)

    try:

        validator.validate(url)

        print("ALLOWED")

    except UnsafeUrlError as ex:

        print(f"BLOCKED: {ex}")