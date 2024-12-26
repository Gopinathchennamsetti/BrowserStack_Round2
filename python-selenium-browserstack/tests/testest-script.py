executor_object = {
    'action': 'setSessionStatus',
    'arguments': {
        'status': "<passed/failed>",
        'reason': "<reason>"
    }
}
browserstack_executor = 'browserstack_executor: {}'.format(json.dumps(executor_object))
driver.execute_script(browserstack_executor)