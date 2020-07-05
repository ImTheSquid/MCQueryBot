import getopt
import json
import socket
import sys
from os import path

import discord
from mcstatus import MinecraftServer


class DataLoader:
    config = {'token': '', 'server': '', 'port': 25565, 'channel': ''}

    def __init__(self, data_args: dict, gen: bool):
        if len(data_args) > 0 and not gen:
            self.load_config()

        if 'token' in data_args:
            self.config['token'] = data_args['token']
        if 'server' in data_args:
            self.config['server'] = data_args['server']
        if 'port' in data_args:
            self.config['port'] = data_args['port']

        if len(data_args) > 0:
            self.generate_config()

    def generate_config(self):
        with open('config.json', 'w') as f:
            json.dump(self.config, f)

    def load_config(self):
        with open('config.json', 'r') as f:
            self.config = json.load(f)

    def get_token(self) -> str:
        return self.config['token']

    def get_channel(self) -> str:
        return self.config['channel']

    def get_server_info(self) -> tuple:
        return self.config['server'], self.config['port']

    def set_channel(self, channel: str):
        self.config['channel'] = channel
        self.generate_config()


class Client(discord.Client):
    loader = None
    server = None
    # Prevents duplicate initialization messages if connection lost, but still sends to console
    init_complete = False

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        if self.loader is not None and len(self.loader.get_channel()) > 0:
            channel_names = [n.name for n in self.get_all_channels()]
            if self.loader.get_channel() not in channel_names or self.init_complete:
                return
            else:
                self.init_complete = True
                channels = [c for c in self.get_all_channels()]
                await channels[channel_names.index(self.loader.get_channel())].send(':white_check_mark: '
                                                                                    'Initialization '
                                                                                    'successful.')

    async def on_message(self, message):
        if not message.content.startswith('mc!'):
            return
        if len(self.loader.get_channel()) > 0 and not message.channel.name == self.loader.get_channel():
            return
        role_names = [n.name for n in message.author.roles]
        command = message.content[len('mc!'):]
        print('Message from {0.author}: {0.content}'.format(message))

        if command == 'exit' and 'Bot Manager' in role_names:
            await message.channel.send(':stop_button: Exiting...')
            await self.logout()
            sys.exit(0)
        elif 'query' in command or 'status' in command:
            use_status = command.startswith('status')
            if len(command.split(' ')) == 1:
                if self.server is None:
                    await message.channel.send(':x: Server object not connected. Could not get status.')
                    return
                if self.loader is None:
                    await message.channel.send(':x: Loader object not connected. Could not get status.')
                    return
            if use_status:
                await message.channel.send(':arrows_counterclockwise: Getting server status, this may take a while...')
            else:
                await message.channel.send(':arrows_counterclockwise: Querying server, this may take a while...')
            try:
                if len(command.split(' ')) == 1:
                    if use_status:
                        query = self.server.status()
                    else:
                        query = self.server.query()
                    server_info = self.loader.get_server_info()
                    print_ip = server_info[0]
                    print_port = server_info[1]
                else:
                    ip_port = command.split(' ')[1]
                    if len(ip_port[1].split(':')) == 2:
                        combo_list = ip_port.split(':', 1)
                        ip = combo_list[0]
                        port = combo_list[1]
                    else:
                        ip = ip_port
                        port = 25565
                    if use_status:
                        query = MinecraftServer(ip, port).status()
                    else:
                        query = MinecraftServer(ip, port).query()
                    print_ip = ip
                    print_port = port
            except socket.timeout:
                if not use_status:
                    await message.channel.send(':x: Error querying server. The server may be offline. '
                                               'Make sure `enable-query` is set to `true` '
                                               'in the `server.properties` file. Try using the `status` command '
                                               'instead.')
                else:
                    await message.channel.send(':x: Error querying server. The server may be offline.')
            else:
                print_data = []
                max_play = 0
                current = 0
                if use_status and query.players.sample is not None:
                    for item in query.players.sample:
                        print_data.append(item.name)
                elif not use_status:
                    print_data = query.players.names
                    max_play = query.players.max
                    current = query.players.online
                if use_status:
                    max_play = query.players.max
                    current = query.players.online
                if len(print_data) > 0:
                    await message.channel.send(':white_check_mark: Server with address `{0}:{1}` is online.'
                                               ' Players [{2}/{3}]: `{4}` '
                                               .format(print_ip, print_port, current, max_play, ', '.join(print_data)))
                else:
                    await message.channel.send(':white_check_mark: Server with address `{0}:{1}` is online. No one is '
                                               'online. '
                                               .format(print_ip, print_port))
        elif command == 'start-server' or command == 'start':
            if not path.isfile('start.sh'):
                await message.channel.send(':x: No `start.sh` file found. Please add file and mark it as executable.')
                return

            await message.channel.send(':arrows_counterclockwise: Querying server, this may take a while...')
            try:
                self.server.status()
            except socket.timeout:
                await message.channel.send(':white_check_mark: Executing script...')
                import subprocess
                subprocess.Popen('~/Bots/MCQBot/start.sh', shell=True)
            else:
                await message.channel.send(':x: The server is currently online.')
        elif command == 'help':
            embed = discord.Embed(title='Help', description='All commands marked with "*" require the "Bot Manager" '
                                                            'role. If you do not have that role and try to use one of '
                                                            'the *\'d commands, the bot will not recognize the '
                                                            'command.',
                                  color=0x4287f5)
            embed.add_field(name='`query [ip:port]`', value='Queries current server status. Adding an IP with an '
                                                            'optional port will query the specified IP.', inline=False)
            embed.add_field(name='`status [ip:port]`', value='Same arguments as `query`, but uses different command '
                                                             'that always works for servers version 1.7+.',
                            inline=False)
            embed.add_field(name='`start-server`', value='Starts server if crashed.', inline=False)
            embed.add_field(name='`start`', value='Same function as `start-server` command.', inline=False)
            embed.add_field(name='`set-channel <channel>`', value='* Sets sole response channel. Pass `~` to respond to'
                                                                  ' all channels.',
                            inline=False)
            embed.add_field(name='`exit`', value='Exits bot.', inline=False)
            embed.add_field(name='`help`', value='Prints help document.', inline=False)
            await message.channel.send(embed=embed)
        elif 'set-channel' in command and 'Bot Manager' in role_names:
            if self.loader is None:
                await message.channel.send(':x: Loader object not connected. Could not set channel.')
                return

            if not len(command.split(' ')) == 2:
                await message.channel.send(':x: Incorrect number of arguments.')
                return

            channel = command.split(' ')[1]
            # Accept all channels
            if channel == '~':
                await message.channel.send(':white_check_mark: Set to accept all channels.')
                self.loader.set_channel('')
                return
            channel_names = [n.name for n in self.get_all_channels()]
            if channel not in channel_names:
                await message.channel.send(':x: Invalid channel.')
            else:
                await message.channel.send(':white_check_mark: Channel set to "#{0}".'.format(channel))
                self.loader.set_channel(channel)
        else:
            await message.channel.send(':question: Command not recognized.')

    def set_loader(self, loader: DataLoader):
        self.loader = loader

    def set_server(self, server: MinecraftServer):
        self.server = server


# Check for args
args = sys.argv
arg_list = args[1:]
unix_options = 'gt:s:p:'
gnu_options = ['generate', 'token=', 'server=', 'port=']
try:
    arguments, values = getopt.getopt(arg_list, unix_options, gnu_options)
except getopt.error as err:
    # Output error and return with an error code
    print(str(err))
    sys.exit(2)
generate = False
data_dict = {}
for current_arg, current_val in arguments:
    if current_arg in ('-g', '--generate'):
        generate = True
    elif current_arg in ('-t', '--token'):
        data_dict['token'] = current_val
    elif current_arg in ('-s', '--server'):
        data_dict['server'] = current_val
    elif current_arg in ('-p', '--port'):
        data_dict['port'] = int(current_val)

if not path.isfile('config.json'):
    generate = True
data = DataLoader(data_dict, generate)

data.load_config()
if data.get_token() == '':
    # Exit if no token found
    print('No token found')
    sys.exit(0)
client = Client()
client.set_loader(data)
info = data.get_server_info()
client.set_server(MinecraftServer(info[0], info[1]))
client.run(data.get_token())
