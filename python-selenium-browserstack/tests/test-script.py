executor_object = {
    'action': 'setSessionName',
    'arguments': {
        'name': "<test-name>"
    }
}
browserstack_executor = 'browserstack_executor: {}'.format(json.dumps(executor_object))
driver.execute_script(browserstack_executor)