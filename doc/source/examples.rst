Examples
==============================

Where to get examples
-----------------------------------

- `aioqzone-feed test suits <https://github.com/aioqzone/aioqzone-feed/blob/beta/test/api/test_h5.py>`_ could provide a basic example;
- `Qzone2TG repository <https://github.com/aioqzone/Qzone2TG>`_ is an example in practical project.

Get feed list
---------------------------

Here is an example (with zh-CN comments!) about how to:

1. initialize a login manager and an API instance
2. register hooks
3. start a fetch process and block until all feeds are processed

.. literalinclude:: _static\example.py
    :language: python
    :linenos:
