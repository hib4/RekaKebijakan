import os

import uvicorn


if __name__ == "__main__":
    uvicorn.run(
        "app:create_app",
        factory=True,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "5001")),
        workers=1,
    )
