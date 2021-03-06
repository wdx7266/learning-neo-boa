from boa.interop.System.Storage import *
from boa.interop.System.Runtime import *

from boa.interop.Neo.Action import RegisterAction
from boa.interop.System.ExecutionEngine import *
from boa.interop.Ontology.Native import *
from boa.interop.Neo.Blockchain import *
from boa.interop.Neo.Block import *
from boa.builtins import *

ctx = GetContext()
contract_address = bytearray(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01')

OnTransfer = RegisterAction('transfer', 'address_from', 'address_to', 'amount')
decimal = 9


def create_template(rule):
    """
    :param rule: list
    :return: bool
    """
    try:
        str_value = ''
        percent = 0
        for q in range(0, len(rule)):
            str_value = str_value + str(rule[q])
            percent += rule[q]
        if percent > 10000:
            return False
        template_id = sha256(str_value)
        Put(ctx, template_id, rule)
        Log(template_id)
        Put(ctx, concat(template_id, 'count'), 0)
        return True
    except Exception:
        return False


def create_instance(template_id, metadata, payments, payer_threshold, payee_threshold, payees, reviewer):
    """
    :param template_id: int
    :param metadata: str
    :param payments: tuple
    :param payer_threshold: int
    :param payee_threshold: int
    :param payees: list
    :param reviewer: str
    :return: bool
    """
    try:
        current_height = GetHeight()
        current_block = GetBlock(current_height)
        current_block_timestamp = current_block.Timestamp
        count = Get(ctx, concat(template_id, 'count'))
        data = concat(template_id, current_block_timestamp)
        data = concat(data, str(count))
        instance_id = hash160(data)
        book = dict()
        Put(ctx, concat(instance_id, 'metadata'), metadata)
        Put(ctx, concat(instance_id, 'payments'), payments)
        Put(ctx, concat(instance_id, 'payer_threshold'), payer_threshold)
        Put(ctx, concat(instance_id, 'payee_threshold'), payee_threshold)
        Put(ctx, concat(instance_id, 'payees'), payees)
        Put(ctx, concat(instance_id, 'reviewer'), reviewer)
        Put(ctx, concat(instance_id, 'balance'), 0)
        Put(ctx, concat(instance_id, 'book'), book)
        Put(ctx, concat(instance_id, 'lock'), False)
        Notify(['create', instance_id])
        count += 1
        Put(ctx, template_id, count)
        return True
    except Exception:
        return False


def input_asset(instance_id, amount, payer):
    """

    :param instance_id: str
    :param amount: int
    :param payer: str
    """
    # check whether instance_id exist
    metadata = Get(ctx, concat(instance_id, 'metadata'))
    if len(metadata) == 0:
        return False
    script_hash = GetExecutingScriptHash()
    is_lock = Get(ctx, concat(instance_id, 'lock'))
    if is_lock:
        return False
    else:
        OnTransfer(payer, script_hash, amount)
        book = Get(ctx, concat(instance_id, 'book'))
        balance = Get(ctx, concat(instance_id, 'balance'))
        balance += amount
        if has_key(book, payer):
            book[payer] += amount
        else:
            book[payer] = amount
        Put(ctx, concat(instance_id, 'book'), book)
        Put(ctx, concat(instance_id, 'balance'), balance)
        Notify(['input', instance_id, amount, payer])


def lock(instance_id, lock_time, lockers):
    """

    :param instance_id: str
    :param lock_time: str
    :param lockers: list
    """
    # check whether instance_id exist
    metadata = Get(ctx, concat(instance_id, 'metadata'))
    if len(metadata) == 0:
        return False
    for index in range(0, len(lockers)):
        CheckWitness(lockers[index])
    is_lock = Get(ctx, concat(instance_id, 'lock'))
    if is_lock:
        return False
    else:
        Put(ctx, concat(instance_id, 'lock'), True)
        Put(ctx, concat(instance_id, 'lockTime'), lock_time)
        Put(ctx, concat(instance_id, 'lockers'), lockers)
        Notify(['Lock', instance_id])
        return True


def confirm(instance_id, confirmer):
    """

    :param instance_id: str
    :param confirmer: list
    """
    # check whether instance_id is exist
    metadata = Get(ctx, concat(instance_id, 'metadata'))
    if len(metadata) == 0:
        return False
    # check lock time
    current_height = GetHeight()
    current_block = GetBlock(current_height)
    current_block_timestamp = current_block.Timestamp
    lock_time = Get(ctx, concat(instance_id, 'lockTime'))
    if current_block_timestamp < lock_time:
        return False
    # check whether already confirmed
    if Get(ctx, concat(instance_id, 'remainBalance')):
        Notify('Already confirmed!')
        return False
    # check whether reviewer is exist
    # if exist, check whether the quota is setting
    reviewer = Get(ctx, concat(instance_id, 'reviewer'))
    if len(reviewer) != 0:
        quota = Get(ctx, concat(instance_id, 'reviewerQuota'))
        if len(quota) == 0:
            return False
    else:
        quota = Get(ctx, instance_id)
    from_acct = GetExecutingScriptHash()
    payees = Get(ctx, concat(instance_id, 'payees'))
    balance = Get(ctx, concat(instance_id, 'balance'))
    remain_balance = balance
    for index in range(0, len(payees)):
        amount = round(balance * quota[index], decimal)
        if remain_balance < amount:
            amount = remain_balance
        param = state(from_acct, payees[index], amount)
        Invoke(amount, contract_address, 'transfer', [param])
        remain_balance -= amount
    Put(ctx, concat(instance_id, 'remainBalance'), remain_balance)
    Put(ctx, concat(instance_id, 'lock'), False)
    Notify(["Confirm", instance_id, confirmer])
    if remain_balance > 0:
        remain_balance(instance_id, confirmer)
    return True


def set_quota(instance_id, quota):
    """

    :param instance_id: str
    :param quota: list
    :return:
    """
    # check whether instance_id exist
    metadata = Get(ctx, concat(instance_id, 'metadata'))
    if len(metadata) == 0:
        return False
    reviewer = Get(ctx, concat(instance_id, 'reviewer'))
    if CheckWitness(reviewer):
        payees = Get(ctx, concat(instance_id, 'payees'))
        if len(payees) > len(quota):
            return False
        else:
            Put(ctx, concat(instance_id, 'reviewerQuota'), quota)
            Notify(['Quota', instance_id, quota])
            return True
    else:
        return False


def refund(instance_id, operator):
    """

    :param instance_id: str
    :param operator: str
    """
    # check whether instance_id exist
    metadata = Get(ctx, concat(instance_id, 'metadata'))
    if len(metadata) == 0:
        return False
    # check whether reviewer exist
    reviewer = Get(ctx, concat(instance_id, 'reviewer'))
    if len(reviewer) == 0:
        return False
    # TODO： 评审人+一方
    if CheckWitness(operator):
        from_acct = GetExecutingScriptHash()
        book = Get(ctx, concat(instance_id, 'book'))
        balance = Get(ctx, concat(instance_id, 'balance'))
        remain_balance = Get(ctx, concat(instance_id, 'remainBalance'))
        for k in keys(book):
            input_sum = book[k]
            amount = round(remain_balance * (input_sum / balance), decimal)
            if remain_balance < amount:
                amount = remain_balance
                param = state(from_acct, k, amount)
                Invoke(amount, contract_address, 'transfer', [param])
                remain_balance -= amount
            Put(ctx, concat(instance_id, 'remainBalance'), remain_balance)
        Notify(['Refund', instance_id, operator])
        return True
    else:
        return False


def main(operation, args):
    """
    This is the main entry point for the Smart Contract

    :param operation: the operation to be performed
    :param args: a list of arguments ( which may be empty, but not absent )
    :return: indicating the successful execution of the smart contract
    """
    if operation == 'create_template':
        create_template(args[0])
        return True
    elif operation == 'create_instance':
        if len(args) == 4:
            return create_instance(args[0], args[1], args[2], args[3], args[4], '')
        elif len(args) == 5:
            return create_instance(args[0], args[1], args[2], args[3], args[4], args[5])
        else:
            return False
    elif operation == 'input_asset':
        if len(args) == 3:
            payer = GetCallingScriptHash()
            if payer != args[2]:
                return False
            return input_asset(args[0], args[1], args[2])
        else:
            return False
    elif operation == 'lock':
        if len(args) == 3:
            return lock(args[0], args[1], args[2])
    elif operation == 'confirm':
        if len(args) == 2:
            return confirm(args[0], args[1])
        else:
            return False
    elif operation == 'set_quota':
        if len(args) == 2:
            return set_quota(args[0], args[1])
        else:
            return False
    elif operation == 'refund':
        if len(args) == 2:
            return refund(args[0], args[1])
        else:
            return False
    else:
        return False


if __name__ == '__main__':
    while True:
        operation = input('operation: ')
        args = input('args: ')
        main(operation, args)
