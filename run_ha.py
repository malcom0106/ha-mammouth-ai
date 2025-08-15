"""Lance Home Assistant avec votre intégration."""
import asyncio
import logging
from homeassistant import core, config
from pathlib import Path

async def main():
    """Lance HA."""
    logging.basicConfig(level=logging.DEBUG)
    
    hass = core.HomeAssistant()
    
    config_dir = Path("./config")
    print(config_dir)
    await hass.async_add_executor_job(config.load_yaml_config_file, 
                                     config_dir / "configuration.yaml")
    
    await hass.async_start()
    
    try:
        await hass.async_block_till_done()
    except KeyboardInterrupt:
        await hass.async_stop()

if __name__ == "__main__":
    asyncio.run(main())
