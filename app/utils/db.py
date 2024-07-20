import psycopg2
import pandas as pd

class WADatabase():
    #### create tables users and surveys for now ###

    def __init__(self, db_config):
        self.conn = self.create_connection(db_config)
        self.create_tables()

    def create_connection(self, db_config):
        try:
            conn = psycopg2.connect(**db_config)
            return conn
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            return None
        
    def create_tables(self):
        with self.conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS users (
                        id SERIAL PRIMARY KEY,
                        phone VARCHAR(32) UNIQUE NOT NULL,
                        has_completed_survey BOOLEAN DEFAULT FALSE
                        );""")
            
            cur.execute("""CREATE TABLE IF NOT EXISTS surveys (
                        id SERIAL PRIMARY KEY,
                        age_group VARCHAR(32),
                        production_experience VARCHAR(8),
                        experience_years VARCHAR(8),
                        marital_status VARCHAR(8),
                        children_status VARCHAR(8),
                        completed_survey BOOLEAN,
                        phone VARCHAR(16) UNIQUE NOT NULL,
                        FOREIGN KEY (phone) REFERENCES users (phone)
                        );""")

            create_table_query = '''
                        CREATE TABLE IF NOT EXISTS vacancies (
                            id SERIAL PRIMARY KEY,
                            title VARCHAR(255) NOT NULL,
                            requirements TEXT,
                            details TEXT,
                            tasks TEXT,
                        );'''
            cur.execute(create_table_query)

            cur.execute('''
                CREATE TABLE IF NOT EXISTS resumes (
                    id SERIAL PRIMARY KEY,
                    user_phone VARCHAR(20),
                    resume_filename VARCHAR(255),
                    resume_data BYTEA,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sent BOOLEAN DEFAULT FALSE
                );
            ''')

            self.conn.commit()

    def get_user(self, phone):
        with self.conn.cursor() as cur:
            cur.execute(
                """
                    SELECT phone from users WHERE phone = %s
                """, (phone)
            )
            user  = cur.fetchone() # fetch phone number
            cur.close()
            return user # should return count of users instead of some user variable?
    
    def create_user(self, phone):
        with self.conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO users (phone) VALUES (%s) ON CONFLICT (phone) DO NOTHING", (phone,))
                self.conn.commit()
            except Exception as e:
                self.conn.rollback()
                print(f"Error inserting user: {e}")
                # logging.info(f'Error inserting a user: {e}')

    def save_survey_results(self, phone, results):
        with self.conn.cursor() as cur: # in the table surveys
            cur.execute(
                """
                    UPDATE surveys SET 
                    age_group = %s,
                    production_experience = %s,
                    experience_years = %s,
                    marital_status = %s,
                    children_status = %s,
                    completed_survey = TRUE
                    WHERE phone = %s
                """, (results['age_group'], results['production_experience'], results['experience_years'], results['marital_status'], results['children_status'], phone )
            )
            cur.execute("UPDATE users SET has_completed_survey = TRUE WHERE phone = %s", (phone,))

    def has_completed_survey(self, phone):
        with self.conn.cursor() as cur:
            cur.execute("SELECT has_completed_survey FROM users WHERE phone = %s", (phone,))
            result = cur.fetchone()
            return result and result[0]

    ######## VACANCIES ##############

    def get_vacancies(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id, title FROM vacancies")
            return cursor.fetchall()
        
    def get_vacancies_with_details(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id, title, tasks, details FROM vacancies")
            return cursor.fetchall()

    def get_vacancy_details(self, vacancy_id):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT title, requirements, details FROM vacancies WHERE id=%s", (vacancy_id,))
            df = cursor.fetchone()
            return df
        

    def get_vacancies_for_interactive_message(self):
        vacancies = self.get_vacancies_with_details()
        sections = [{
            "title": "Доступные вакансии",
            "rows": [{"id": str(vac[0]), "title": vac[1], "details": vac[2], "tasks": vac[3]} for vac in vacancies]
        }]
        return sections

    def insert_resume(self, user_phone, resume_filename, resume_data):
        with self.connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO resumes (user_phone, resume_filename, resume_data)
                VALUES (%s, %s, %s)
                """,
                (user_phone, resume_filename, resume_data)
            )
            self.connection.commit()

    def get_resumes_older_than(self, days):
        with self.connection.cursor() as cursor:
            query = """
                SELECT user_phone, user_address, resume_filename, resume_data
                FROM resumes
                WHERE created_at <= NOW() - INTERVAL '%s days'
                AND sent = FALSE
            """
            cursor.execute(query, (days,))
            return cursor.fetchall()

    def mark_resumes_as_sent(self, resumes):
        with self.connection.cursor() as cursor:
            query = """
                UPDATE resumes
                SET sent = TRUE
                WHERE id = ANY(%s)
            """
            resume_ids = [resume['id'] for resume in resumes]
            cursor.execute(query, (resume_ids,))
            self.connection.commit()