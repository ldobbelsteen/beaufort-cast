```
docker run -d \
    --name beaufort-cast \
    --restart always \
    --network host \
    --volume {dir}:/photos:ro \
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

- `PHOTO_DIR` is het pad naar de map met alle foto's
- `CAST_DEVICE_NAME` is de naam van het Chromecast apparaat om naar te casten
- `LOCAL_IP` het IP adres van het apparaat waar dit programma op draait
- `LISTENING_PORT` de poort waarop de foto's gehost mogen worden op dit apparaat
- `BLACKLISTED_DIR_NAMES` niet-hoofdlettergevoelige lijst van verboden woorden in mappen (gescheiden door een `;`)
- `CAST_CHECK_INTERVAL_SECS` aantal seconden tussen het checken of de Chromecast beschikbaar is
- `NEXT_PHOTO_INTERVAL_SECS` aantal seconden tussen het wisselen van foto's
- `PHOTO_INDEX_INTERVAL_SECS` aantal seconden tussen het opnieuw scannen van alle foto's (voor het detecteren van nieuwe foto's, verwijderde foto's, etc.)
