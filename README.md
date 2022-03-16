# aioqzone-feed

An [aioqzone][aioqzone] plugin for handling feeds, a high-level api for feed operation.

[![python](https://img.shields.io/badge/python-3.7%20%7C%203.10-blue)][home]
[![Dev CI](https://github.com/JamzumSum/aioqzone-feed/actions/workflows/ci.yml/badge.svg)](https://github.com/JamzumSum/aioqzone-feed/actions/workflows/ci.yml)
[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

## Feature

- [x] Fetch feeds easily
- [x] Optimize for 311 feeds
- [x] Lazy update for raw photos and videos
- [x] Inner heartbeat management
- [x] Qzone emoji translate ([QzEmoji][qzemoji])
- [x] All in async
- [x] Hook support

## Usage

- API: all in `api.feed.FeedApi`:
    - `api.feed.FeedApi.get_feeds_by_count`
    - `api.feed.FeedApi.get_feeds_by_second`
    - `api.feed.FeedApi.add_heartbeat`: Start heartbeat
    - `api.feed.FeedApi.wait`: Wait for all dispatch and hook tasks
    - `api.feed.FeedApi.wait`: Stop and clean all registered tasks.
- Hooks: all in `interface.hook`
    - `interface.hook.FeedEvent.FeedDropped`: Feed is dropped for hitting some rules (e.g. advertisement)
    - `interface.hook.FeedEvent.FeedProcEnd`: All processes must be done have finished (i.e. except for slow-api that cannot return at once, and may not matters a lot)
    - `interface.hook.FeedEvent.FeedMediaUpdate`: One of the slow api. The media should be update by raw photos/videos, list order should not be changed.
    - `interface.hook.FeedEvent.HeartbeatRefresh`: This event is triggered after a heartbeat succeeded and there are new feeds.
    - `interface.hook.FeedEvent.HeartbeatFailed`: Heartbeat failed and will not trigged again. One may call `api.feed.FeedApi.add_heartbeat` again.

## License

- [AGPL-3.0](LICENSE)
- `aioqzone-feed` is a plugin of [aioqzone][aioqzone]. This repository inherits license, instructions and any other requirements from `aioqzone`. See also: [License fragment in aioqzone README file](https://github.com/JamzumSum/aioqzone#license)


[aioqzone]: https://github.com/JamzumSum/aioqzone "Python wrapper for Qzone web login and Qzone http api."
[qzemoji]: https://github.com/JamzumSum/QzEmoji/tree/async "Translate Qzone emoji to text"
[home]: https://github.com/JamzumSum/aioqzone-feed "aioqzone plugin providing higher level api for processing feed"
