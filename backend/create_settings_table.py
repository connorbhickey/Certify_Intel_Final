from database import engine, Base, SystemSetting

# Create the table
print("Creating system_settings table...")
SystemSetting.__table__.create(engine)
print("Table created successfully!")
