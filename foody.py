import discord

from discord.ext import commands
from discord.ext.commands import DefaultHelpCommand

from time import time
from collections import OrderedDict


bot_command_prefix = '$'
bot_token = '<YOUR_BOT_TOKEN_HERE>'


class FoodyHelpCommand(DefaultHelpCommand):
    def __init__(self):
        super().__init__()
        self.no_category = f'Command prefix: \'{bot_command_prefix}\'\n\nCommands'
        self.indent = 0
        self.command_attrs['hidden'] = True
        self.command_attrs['help'] = f'Shows information about available commands. ' \
                                     f'Can be invoked without any arguments to show available commands ' \
                                     f'or with a command name to show its description.\n\n' \
                                     f'Examples:\n{bot_command_prefix}help\n{bot_command_prefix}help order'

    def get_ending_note(self):
        command_name = self.invoked_with
        return f'Type {self.clean_prefix}{command_name} <command_name> for more information on a command.\n'


class Order:
    def __init__(self, order_content):
        self.order_content = order_content


class GroupOrder:
    def __init__(self, restaurant_name):
        self.restaurant_name = restaurant_name
        self.timestamp = time()
        self.orders_dict = OrderedDict()


bot = commands.Bot(command_prefix=bot_command_prefix,
                   help_command=FoodyHelpCommand(),
                   activity=discord.Activity(name=f'DM {bot_command_prefix}help for info',
                                             type=discord.ActivityType.playing))

start_order_command_name = 'order_start'
order_item_command_name = 'order'
list_orders_command_name = 'order_list'
tag_all_in_order_command_name = 'order_tag'
leave_order_command_name = 'order_leave'

confirmation_needed_time_threshold = 2  # in hours

group_orders_dict = {}
awaiting_confirmation_dict = {}


async def initialize_new_order(ctx, restaurant_name):
    awaiting_confirmation_dict.pop(ctx.channel, None)
    group_orders_dict[ctx.channel] = GroupOrder(restaurant_name)
    await ctx.send(f'Taking orders for **{restaurant_name}**\n@here')


def order_awaits_confirmation(channel, restaurant_name):
    return channel in awaiting_confirmation_dict \
           and awaiting_confirmation_dict[channel].restaurant_name == restaurant_name


def order_needs_confirmation(channel, restaurant_name):
    if channel not in group_orders_dict:
        return False
    if order_old_enough_to_overwrite(group_orders_dict[channel]):
        return False
    if order_awaits_confirmation(channel, restaurant_name):
        return False
    return True


def order_old_enough_to_overwrite(order):
    return time() - order.timestamp > confirmation_needed_time_threshold * 60 * 60


async def send_confirmation_request(ctx, restaurant_name, current_group_order):
    awaiting_confirmation_dict[ctx.channel] = GroupOrder(restaurant_name)
    await ctx.send(f'There is a recent (not older than {confirmation_needed_time_threshold} hour(s)) '
                   f'group order active in this channel with {len(current_group_order.orders_dict)} '
                   f'order(s) already placed.\n'
                   f'You can use a different channel to initialize your group order or '
                   f'overwrite the current one by sending the same request again.')


@bot.command(name=start_order_command_name,
             brief='Start a new group order',
             help=f'Starts a new group order for given restaurant. '
                  f'Only one group order can be active on a given channel. '
                  f'If you want to overwrite the currently active group order just try starting a new one. '
                  f'If the currently active order is not older than {confirmation_needed_time_threshold} hour(s) '
                  f'you will be asked to confirm the overwrite otherwise the order will be overwritten immediately.\n\n'
                  f'Example:\n{bot_command_prefix}{start_order_command_name} "The Prancing Pony"\n\n'
                  f'Note: Phrases containing spaces have to be put in double quotes.')
async def start_new_order(ctx, restaurant_name):
    if order_needs_confirmation(ctx.channel, restaurant_name):
        await send_confirmation_request(ctx, restaurant_name, group_orders_dict[ctx.channel])
    else:
        await initialize_new_order(ctx, restaurant_name)


async def add_item_to_order(ctx, order_content, with_warning):
    group_order = group_orders_dict[ctx.channel]
    order = Order(order_content)
    group_order.orders_dict[ctx.author] = order
    message_string = f'You\'ve just ordered ```{order_content}``` from **{group_order.restaurant_name}** ' \
                     f'on the "{ctx.channel.name}" channel.\n\n'
    if with_warning:
        message_string += f'WARNING: The order has been placed but note that the currently active group order ' \
                          f'on this channel is older than {confirmation_needed_time_threshold} hour(s).'
    await ctx.author.send(message_string)


@bot.command(name=order_item_command_name,
             brief='Add order to the group order',
             help=f'Allows you to add your order to the currently active group order. '
                  f'Any subsequent calls of this command will overwrite your previous order '
                  f'as opposed to adding a new one. After ordering you will receive a DM confirming the action.\n\n'
                  f'Example:\n{bot_command_prefix}{order_item_command_name} "Can I have a hamburger please?!"\n\n'
                  f'Note: Phrases containing spaces have to be put in double quotes.')
async def order_item(ctx, order_content):
    if ctx.channel not in group_orders_dict:
        await ctx.send('No active group order on this channel')
    else:
        await add_item_to_order(ctx, order_content, order_old_enough_to_overwrite(group_orders_dict[ctx.channel]))


def generate_orders_list_string(group_order):
    if len(group_order.orders_dict) == 0:
        return 'No orders placed'
    list_string = ''
    for user, order in group_order.orders_dict.items():
        list_string += f'{user.display_name}: {order.order_content}\n'
    return list_string


def generate_order_list_message_string(group_order):
    message_string = f'Group order for **{group_order.restaurant_name}** ```'
    message_string += generate_orders_list_string(group_order)
    message_string += '```'
    return message_string


async def list_orders_in_group_order(ctx, group_order):
    message_string = generate_order_list_message_string(group_order)
    await ctx.send(message_string)


@bot.command(name=list_orders_command_name,
             brief='List all orders in the group order',
             help=f'Shows the name of the restaurant the group order is for '
                  f'as well as listing all the users taking part in the group order '
                  f'together with their individual orders.\n\n'
                  f'Example:\n'
                  f'{bot_command_prefix}{list_orders_command_name}')
async def list_orders_in_current_group_order(ctx):
    if ctx.channel not in group_orders_dict:
        await ctx.send('No active group order on this channel')
    else:
        await list_orders_in_group_order(ctx, group_orders_dict[ctx.channel])


def generate_tag_message_string(message, group_order):
    message_string = f'{message}\n\n'
    for user in group_order.orders_dict:
        message_string += f'{user.mention} '
    return message_string


async def send_message_and_tag_users_in_order(ctx, message, group_order):
    message_string = generate_tag_message_string(message, group_order)
    await ctx.send(message_string)


@bot.command(name=tag_all_in_order_command_name,
             brief='Send a message and tag users in the group order',
             help=f'Sends a given message and tags all the users that are taking part '
                  f'in the currently active group order.\n\n'
                  f'Example:\n{bot_command_prefix}{tag_all_in_order_command_name} "Pizza time!"\n\n'
                  f'Note: Phrases containing spaces have to be put in double quotes.')
async def send_message_and_tag_users_in_current_order(ctx, message):
    if ctx.channel not in group_orders_dict:
        await ctx.send('No active group order on this channel')
    else:
        await send_message_and_tag_users_in_order(ctx, message, group_orders_dict[ctx.channel])


async def remove_user_from_order(user, group_order, channel):
    if group_order.orders_dict.pop(user, None) is None:
        await user.send(f'You\'ve just tried to leave a group order you are not a part of (on the "{channel.name}" channel).')
    else:
        await user.send(f'You\'ve just left a group order for **{group_order.restaurant_name}** '
                        f'on the "{channel.name}" channel.')


@bot.command(name=leave_order_command_name,
             brief='Leave a group order',
             help=f'Allows you to leave the currently active group order. '
                  f'After leaving you will receive a DM confirming the action.\n\n'
                  f'Example:\n{bot_command_prefix}{leave_order_command_name}')
async def leave_current_order(ctx):
    if ctx.channel not in group_orders_dict:
        await ctx.send('No active group order on this channel')
    else:
        await remove_user_from_order(ctx.author, group_orders_dict[ctx.channel], ctx.channel)


bot.run(bot_token)
