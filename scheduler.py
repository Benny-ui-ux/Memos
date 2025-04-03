from apscheduler.schedulers.blocking import BlockingScheduler
from app import check_and_send_reminders, app, logger
from datetime import datetime

scheduler = BlockingScheduler()

@scheduler.scheduled_job("interval", minutes=1)
def run_scheduled_task():
    logger.info(f"Running scheduled check at {datetime.utcnow()}")
    with app.app_context():
        check_and_send_reminders()
    logger.info("Completed scheduled check")

if __name__ == "__main__":
    logger.info("Starting scheduler...")
    scheduler.start()