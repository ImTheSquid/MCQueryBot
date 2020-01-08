import getopt
import json
import os.path as path
import socket
import sys

import discord
from mcstatus import MinecraftServer


class DataLoader:
    config = {'token': '', 'server': '', 'port': 25565, 'channel': ''}

    def __init__(self, data_args: dict, gen: bool):
        if 'token' in data_args:
            self.config['token'] = data_args['token']
        elif 'server' in data_args:
            self.config['server'] = data_args['server']
        elif 'port' in data_args:
            self.config['port'] = data_args['port']

        if gen:
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

    async def on_ready(self):
        print('Logged on as {0}!'.format(self.user))
        if self.loader is not None and len(self.loader.get_channel()) > 0:
            channelNames = [n.name for n in self.get_all_channels()]
            if self.loader.get_channel() not in channelNames:
                return
            else:
                channels = [c for c in self.get_all_channels()]
                await channels[channelNames.index(self.loader.get_channel())].send(':white_check_mark: '
                                                                                   'Initialization '
                                                                                   'successful.')

    async def on_message(self, message):
        if not message.content.startswith('mc!'):
            return
        if len(self.loader.get_channel()) > 0 and not message.channel.name == self.loader.get_channel():
            return
        roleNames = [n.name for n in message.author.roles]
        command = message.content[len('mc!'):]
        print('Message from {0.author}: {0.content}'.format(message))

        if command == 'exit' and 'Bot Manager' in roleNames:
            await message.channel.send(':stop_button: Exiting...')
            await self.logout()
            sys.exit(0)
        elif command == 'query':
            if self.server is None or self.loader is None:
                await message.channel.send(':x: Server object or loader object not connected. Could not get status.')
                return

            await message.channel.send(':arrows_counterclockwise: Querying server, this may take a while...')
            try:
                query = self.server.query()
            except socket.timeout:
                await message.channel.send(':x: Error querying server. The server may be offline. '
                                           'Make sure `enable-query` is set to `true` '
                                           'in your `server.properties` file.')
            else:
                serverInfo = self.loader.get_server_info()
                if len(query.players.names) > 0:
                    await message.channel.send(':white_check_mark: Server with address `{0}:{1}` is online. Players: '
                                               '`{2}` '
                                               .format(serverInfo[0], serverInfo[1], ', '.join(query.players.names)))
                else:
                    await message.channel.send(':white_check_mark: Server with address `{0}:{1}` is online. No one is '
                                               'online. '
                                               .format(serverInfo[0], serverInfo[1]))
        elif command == 'start-server':
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
            embed = discord.Embed(title="Help", description='All commands marked with "*" require the "Bot Manager" '
                                                            'role. If you do not have that role and try to use one of '
                                                            'the *\'d commands, the bot will not respond.',
                                  color=0x4287f5)
            embed.add_field(name="query", value="Queries current server status.", inline=False)
            embed.add_field(name="start-server", value="Starts server if crashed.", inline=False)
            embed.add_field(name="set-channel <channel>", value="* Sets sole response channel. Pass '~' to respond to "
                                                                "all channels.",
                            inline=False)
            embed.add_field(name="exit", value="* Exits bot.", inline=False)
            embed.add_field(name="help", value="Prints help document.", inline=False)
            await message.channel.send(embed=embed)
        elif 'set-channel' in command and 'Bot Manager' in roleNames:
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
            channelNames = [n.name for n in self.get_all_channels()]
            if channel not in channelNames:
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
argList = args[1:]
unixOptions = 'gt:s:p:'
gnuOptions = ['generate', 'token=', 'server=', 'port=']
try:
    arguments, values = getopt.getopt(argList, unixOptions, gnuOptions)
except getopt.error as err:
    # output error, and return with an error code
    print(str(err))
    sys.exit(2)
generate = False
dataArgs = {}
for currentArg, currentVal in arguments:
    if currentArg in ('-g', '--generate'):
        generate = True
    elif currentArg in ('-t', '--token'):
        dataArgs['token'] = currentVal
    elif currentArg in ('-s', '--server'):
        dataArgs['server'] = currentVal
    elif currentArg in ('-p', '--port'):
        dataArgs['port'] = int(currentVal)

if not path.isfile('config.json'):
    generate = True
data = DataLoader(dataArgs, generate)

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
