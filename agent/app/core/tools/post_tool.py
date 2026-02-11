from langchain_core.tools import tool
import requests

@tool
def create_post(title: str, body: str, user_id: int) -> dict:
    """Creates a new post on the JSONPlaceholder server

    Args:
        title: The title of the post.
        body: The content body of the post.
        user_id: The ID of the user creating the post.
    """
    response = requests.post(
        'https://jsonplaceholder.typicode.com/posts',
        json = {
            'title': title,
            'body': body,
            'userId': user_id
        },
        headers={
            'Content-type': 'application/json; charset=UTF-8'
        }
    )

    return response.json()

@tool
def get_user_posts(user_id: int) -> list:
    """Fetches a list of posts written by a specific user.
    
    Args:
        user_id: The ID of the user to fetch posts for.
    """
    response = requests.get(f'https://jsonplaceholder.typicode.com/posts?userId={user_id}')
    return response.json()