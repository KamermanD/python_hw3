from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from src.core.database import get_async_session
from src.core.logger import logger
from src.services.link import LinkManager
from src.core.config import settings 


class Scheduler:

    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._scheduler = AsyncIOScheduler()
            self._register_jobs()
            self._initialized = True

    def _register_jobs(self):
        self._scheduler.add_job(
            self._clean_expired_links_task,
            IntervalTrigger(minutes=settings.CLEANUP_INTERVAL_MIN),
            id="cleanup_expired_links",
            name="Удаление истекших ссылок",
            replace_existing=True,
        )
        logger.info(
            f"Планировщик, настроенный для выполнения очистки каждый {settings .CLEANUP_INTERVAL_MIN} минут"
        )

    async def _clean_expired_links_task(self):
        try:
            async for session in get_async_session():
                link_service = LinkManager(session)

                logger.debug(" >>> Ввод _clean_expired_links_task")
                deleted_count = await link_service.purge_expired_links()
                logger.debug(" >>> Вывод _clean_expired_links_task")

                logger.info(f"Приведен в порядок {deleted_count} ссылки с истекшим сроком действия")
        except Exception as e:
            logger.exception(f"Ошибка при очистке просроченных ссылок: {e}")

    def start(self):
        self._scheduler .start()
        logger.info("Scheduler запущен")

    def stop(self):
        self._scheduler .shutdown()
        logger.info("Scheduler остановлен")
