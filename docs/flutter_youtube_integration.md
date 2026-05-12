# Pixelo Flutter YouTube Integration

Add these packages to `pubspec.yaml`:

```yaml
dependencies:
  http: ^1.2.2
  youtube_player_flutter: ^9.1.1
  video_player: ^2.9.2
  chewie: ^1.8.5
```

## Data Model

`lib/features/youtube_videos/data/youtube_video.dart`

```dart
class YouTubeVideo {
  final String title;
  final String thumbnail;
  final String videoId;
  final String channelName;

  const YouTubeVideo({
    required this.title,
    required this.thumbnail,
    required this.videoId,
    required this.channelName,
  });

  factory YouTubeVideo.fromJson(Map<String, dynamic> json) {
    return YouTubeVideo(
      title: json['title'] as String? ?? '',
      thumbnail: json['thumbnail'] as String? ?? '',
      videoId: json['videoId'] as String? ?? '',
      channelName: json['channelName'] as String? ?? '',
    );
  }
}
```

## API Service

`lib/features/youtube_videos/data/youtube_video_api.dart`

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'youtube_video.dart';

class YouTubeVideoApi {
  final String baseUrl;
  final http.Client _client;

  YouTubeVideoApi({
    required this.baseUrl,
    http.Client? client,
  }) : _client = client ?? http.Client();

  Future<List<YouTubeVideo>> fetchHomeVideos() {
    return _fetch('/api/home-videos/');
  }

  Future<List<YouTubeVideo>> fetchReelsVideos() {
    return _fetch('/api/reels-videos/');
  }

  Future<List<YouTubeVideo>> _fetch(String path) async {
    final uri = Uri.parse('$baseUrl$path');
    final response = await _client.get(uri);

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Unable to load videos');
    }

    final decoded = jsonDecode(response.body) as Map<String, dynamic>;
    final videos = decoded['videos'] as List<dynamic>? ?? const [];
    return videos
        .map((item) => YouTubeVideo.fromJson(item as Map<String, dynamic>))
        .where((video) => video.videoId.isNotEmpty)
        .toList();
  }
}
```

## Reusable Player

`lib/features/youtube_videos/widgets/pixelo_youtube_player.dart`

```dart
import 'package:flutter/material.dart';
import 'package:youtube_player_flutter/youtube_player_flutter.dart';

class PixeloYouTubePlayer extends StatefulWidget {
  final String videoId;
  final bool autoPlay;
  final bool fullScreen;

  const PixeloYouTubePlayer({
    super.key,
    required this.videoId,
    this.autoPlay = false,
    this.fullScreen = false,
  });

  @override
  State<PixeloYouTubePlayer> createState() => _PixeloYouTubePlayerState();
}

class _PixeloYouTubePlayerState extends State<PixeloYouTubePlayer> {
  late final YoutubePlayerController _controller;

  @override
  void initState() {
    super.initState();
    _controller = YoutubePlayerController(
      initialVideoId: widget.videoId,
      flags: YoutubePlayerFlags(
        autoPlay: widget.autoPlay,
        mute: false,
        loop: widget.fullScreen,
        controlsVisibleAtStart: !widget.fullScreen,
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant PixeloYouTubePlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.autoPlay != widget.autoPlay) {
      widget.autoPlay ? _controller.play() : _controller.pause();
    }
  }

  @override
  Widget build(BuildContext context) {
    return YoutubePlayerBuilder(
      player: YoutubePlayer(controller: _controller, showVideoProgressIndicator: true),
      builder: (_, player) => player,
    );
  }
}
```

## Home Feed Widget

`lib/features/home/home_video_feed.dart`

```dart
import 'package:flutter/material.dart';

import '../youtube_videos/data/youtube_video_api.dart';
import '../youtube_videos/data/youtube_video.dart';
import '../youtube_videos/widgets/pixelo_youtube_player.dart';

class HomeVideoFeed extends StatelessWidget {
  final YouTubeVideoApi api;

  const HomeVideoFeed({super.key, required this.api});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<YouTubeVideo>>(
      future: api.fetchHomeVideos(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return const Center(child: Text('Could not load educational videos.'));
        }
        final videos = snapshot.data ?? const [];
        return ListView.builder(
          itemCount: videos.length,
          itemBuilder: (context, index) {
            final video = videos[index];
            return Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                PixeloYouTubePlayer(videoId: video.videoId),
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(video.title, style: Theme.of(context).textTheme.titleMedium),
                      const SizedBox(height: 4),
                      Text(video.channelName, style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                ),
                const Divider(height: 1),
              ],
            );
          },
        );
      },
    );
  }
}
```

## Reels Widget

`lib/features/reels/reels_video_screen.dart`

```dart
import 'package:flutter/material.dart';

import '../youtube_videos/data/youtube_video.dart';
import '../youtube_videos/data/youtube_video_api.dart';
import '../youtube_videos/widgets/pixelo_youtube_player.dart';

class ReelsVideoScreen extends StatefulWidget {
  final YouTubeVideoApi api;

  const ReelsVideoScreen({super.key, required this.api});

  @override
  State<ReelsVideoScreen> createState() => _ReelsVideoScreenState();
}

class _ReelsVideoScreenState extends State<ReelsVideoScreen> {
  int _activeIndex = 0;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<YouTubeVideo>>(
      future: widget.api.fetchReelsVideos(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        if (snapshot.hasError) {
          return const Scaffold(body: Center(child: Text('Could not load reels.')));
        }
        final videos = snapshot.data ?? const [];
        return Scaffold(
          backgroundColor: Colors.black,
          body: PageView.builder(
            scrollDirection: Axis.vertical,
            onPageChanged: (index) => setState(() => _activeIndex = index),
            itemCount: videos.length,
            itemBuilder: (context, index) {
              final video = videos[index];
              final isActive = index == _activeIndex;
              return Stack(
                fit: StackFit.expand,
                children: [
                  Center(
                    child: AspectRatio(
                      aspectRatio: 9 / 16,
                      child: PixeloYouTubePlayer(
                        videoId: video.videoId,
                        autoPlay: isActive,
                        fullScreen: true,
                      ),
                    ),
                  ),
                  Positioned(
                    left: 16,
                    right: 16,
                    bottom: 32,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text(
                          video.title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 6),
                        Text(video.channelName, style: const TextStyle(color: Colors.white70)),
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        );
      },
    );
  }
}
```
