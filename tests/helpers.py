def csrf_token(client):
    with client.session_transaction() as session:
        token = session.get('_csrf_token')
    if token is None:
        client.get('/')
        with client.session_transaction() as session:
            token = session['_csrf_token']
    return token


def register_client(client, username='testuser', email='test@example.com'):
    client.get('/register')
    response = client.post('/register', data={
        '_csrf_token': csrf_token(client),
        'username': username,
        'email': email,
        'password': 'securepass123',
    })
    assert response.status_code == 302, response.status_code
    return response
