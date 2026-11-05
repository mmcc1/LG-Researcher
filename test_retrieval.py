from retrieval.http import (
    HttpDocumentRetriever,
)
from security.url_validator import (
    UrlValidator,
)


validator = UrlValidator()

retriever = HttpDocumentRetriever(
    url_validator=validator,
)


document = retriever.retrieve(
    "https://bitcoinops.org/en/topics/quantum-resistance/"
)


print("Requested:")
print(document.requested_url)

print()
print("Final:")
print(document.final_url)

print()
print("Status:")
print(document.status_code)

print()
print("Content type:")
print(document.content_type)

print()
print("Bytes:")
print(len(document.content))