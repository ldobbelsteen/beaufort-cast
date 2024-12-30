# Usage

```
docker run -d \
    --name beaufort-cast \
    -v {dir}:/photos:ro \
    --network host \
    --env PHOTO_DIR=/photos \
    --env CAST_DEVICE_NAME=xxx \
    --env LOCAL_IP=xxx \
    --env LISTENING_PORT=xxx \
    --env BLACKLISTED_DIR_NAMES=xxx \
    --env CAST_CHECK_INTERVAL_SECS=xxx \
    --env NEXT_PHOTO_INTERVAL_SECS=xxx \
    --env PHOTO_INDEX_INTERVAL_SECS=xxx \
    ghcr.io/ldobbelsteen/beaufort-cast
```
