import asyncio
from tools.application_filler import auto_apply_to_job

async def main():
    result = await auto_apply_to_job(
        'https://indeed.com/viewjob?jk=test',
        'resume.pdf',
        'https://github.com/user',
        'https://linkedin.com/in/user'
    )
    print("Result:", result)

if __name__ == "__main__":
    asyncio.run(main())
