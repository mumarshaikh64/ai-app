import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:socket_io_client/socket_io_client.dart' as io;

void main() {
  runApp(const PeperIoApp());
}

class PeperIoApp extends StatelessWidget {
  const PeperIoApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Peper.io 2',
      theme: ThemeData.dark(),
      home: const LobbyScreen(),
    );
  }
}

class LobbyScreen extends StatefulWidget {
  const LobbyScreen({super.key});

  @override
  State<LobbyScreen> createState() => _LobbyScreenState();
}

class _LobbyScreenState extends State<LobbyScreen> {
  final nameController = TextEditingController();

  @override
  void dispose() {
    nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Join Match')),
      body: Center(
        child: SizedBox(
          width: 320,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              TextField(
                controller: nameController,
                decoration: const InputDecoration(
                  labelText: 'Player name',
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () {
                  final name = nameController.text.trim();
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => GameScreen(playerName: name.isEmpty ? 'Player' : name),
                    ),
                  );
                },
                child: const Text('Play'),
              )
            ],
          ),
        ),
      ),
    );
  }
}

class GameScreen extends StatefulWidget {
  const GameScreen({super.key, required this.playerName});

  final String playerName;

  @override
  State<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends State<GameScreen> {
  late final io.Socket socket;
  final Map<String, PlayerState> players = {};
  String? selfId;
  int worldSize = 2000;
  Offset inputDirection = Offset.zero;
  Timer? inputTimer;

  @override
  void initState() {
    super.initState();
    socket = io.io(
      'http://localhost:3000',
      io.OptionBuilder().setTransports(['websocket']).build(),
    );

    socket.onConnect((_) {
      socket.emit('join', {'name': widget.playerName});
    });

    socket.on('world:init', (data) {
      setState(() {
        selfId = data['id'] as String?;
        worldSize = data['worldSize'] as int? ?? 2000;
        for (final player in data['players']) {
          final parsed = PlayerState.fromMap(player);
          players[parsed.id] = parsed;
        }
      });
    });

    socket.on('player:joined', (data) {
      final player = PlayerState.fromMap(data);
      setState(() {
        players[player.id] = player;
      });
    });

    socket.on('player:left', (data) {
      setState(() {
        players.remove(data['id']);
      });
    });

    socket.on('world:state', (data) {
      setState(() {
        for (final player in data) {
          final parsed = PlayerState.fromMap(player);
          players[parsed.id] = parsed;
        }
      });
    });

    inputTimer = Timer.periodic(const Duration(milliseconds: 50), (_) {
      socket.emit('input', {'vx': inputDirection.dx, 'vy': inputDirection.dy});
    });
  }

  @override
  void dispose() {
    inputTimer?.cancel();
    socket.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Arena (${players.length})'),
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          return GestureDetector(
            onPanUpdate: (details) {
              final delta = details.delta;
              final length = max(1.0, delta.distance);
              setState(() {
                inputDirection = Offset(delta.dx / length, delta.dy / length);
              });
            },
            onPanEnd: (_) {
              setState(() {
                inputDirection = Offset.zero;
              });
            },
            child: CustomPaint(
              size: Size(constraints.maxWidth, constraints.maxHeight),
              painter: ArenaPainter(players: players, selfId: selfId),
            ),
          );
        },
      ),
    );
  }
}

class PlayerState {
  PlayerState({
    required this.id,
    required this.name,
    required this.x,
    required this.y,
    required this.score,
  });

  final String id;
  final String name;
  final double x;
  final double y;
  final int score;

  factory PlayerState.fromMap(Map<String, dynamic> map) {
    return PlayerState(
      id: map['id'] as String,
      name: map['name'] as String? ?? 'Player',
      x: (map['x'] as num).toDouble(),
      y: (map['y'] as num).toDouble(),
      score: map['score'] as int? ?? 0,
    );
  }
}

class ArenaPainter extends CustomPainter {
  ArenaPainter({required this.players, required this.selfId});

  final Map<String, PlayerState> players;
  final String? selfId;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = Colors.greenAccent;
    final self = selfId != null ? players[selfId] : null;
    final center = Offset(size.width / 2, size.height / 2);

    if (self != null) {
      canvas.translate(center.dx - self.x, center.dy - self.y);
    }

    for (final player in players.values) {
      final isSelf = player.id == selfId;
      paint.color = isSelf ? Colors.orangeAccent : Colors.blueAccent;
      canvas.drawCircle(Offset(player.x, player.y), 12, paint);
      final textPainter = TextPainter(
        text: TextSpan(
          text: player.name,
          style: const TextStyle(color: Colors.white, fontSize: 12),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      textPainter.paint(canvas, Offset(player.x - textPainter.width / 2, player.y - 28));
    }
  }

  @override
  bool shouldRepaint(covariant ArenaPainter oldDelegate) {
    return oldDelegate.players != players || oldDelegate.selfId != selfId;
  }
}
