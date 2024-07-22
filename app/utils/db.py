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
                        has_completed_survey BOOLEAN REFERENCES surveys (completed_survey)
                        );""")
            
            cur.execute("""CREATE TABLE IF NOT EXISTS surveys (
                        id SERIAL PRIMARY KEY,
                        age INT,
                        production_experience VARCHAR(8),
                        completed_survey BOOLEAN,
                        phone VARCHAR(16) UNIQUE NOT NULL,
                        );""")

            create_table_query = '''
                        CREATE TABLE IF NOT EXISTS vacancies (
                            id SERIAL PRIMARY KEY,
                            title VARCHAR(255) NOT NULL,
                            requirements TEXT,
                            details TEXT,
                            tasks TEXT
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
                """, (phone,)
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

    def save_survey_results(self, phone, key, text):
        with self.conn.cursor() as cur:
            # First try to update the record
            cur.execute(
                """
                UPDATE surveys SET 
                {key} = %s
                WHERE phone = %s;
                """.format(key=key), (phone, text,)
            )

            # Check if the record was updated
            if cur.rowcount == 0:
                # If no rows were updated, insert a new record
                cur.execute(
                    """
                    INSERT INTO surveys (phone, {key})
                    VALUES (%s, %s)
                    """.format(key=key), (phone, text,)
                )

            # Commit the transaction
            self.conn.commit()

    def has_completed_survey(self, phone):
        with self.conn.cursor() as cur:
            cur.execute("SELECT has_completed_survey FROM users WHERE phone = %s", (phone,))
            result = cur.fetchone()
            return result
        
    def filling_a_survey(self, phone):
        '''
        returns state and step
        '''
        with self.conn.cursor() as cur:
            cur.execute("SELECT survey_mode, current_step FROM users WHERE phone = %s", (phone,))
            isSurveying, step = cur.fetchone()
            return isSurveying, step
        
    def increment_step(self, phone):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE users SET current_step = current_step + 1 WHERE phone = %s;" (phone,))
            self.conn.commit()

    def set_survey_mode(self, phone, value):
        ''' value is True or False'''
        with self.conn.cursor() as cur:
            cur.execute("UPDATE users SET survey_mode = %s WHERE phone = %s;" (value, phone,))
            self.conn.commit()  # Commit the transaction            

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
        vacancies = self.get_vacancies()
        def shorten_title(title, max_length=24):
            """
            Shortens a given title to a maximum length.
            
            Args:
                title (str): название вакансии.
                max_length (int): максимальная длина заголовка.
                
            Returns:
                str: The shortened title.
            """

            if len(title) > max_length:
                return title[:max_length]  # Truncate the title to the max length
            return title

        sections = [{
            "title": "Доступные вакансии",
            "rows": [{"id": str(vac[0]), "title": shorten_title(vac[1]), "description": ""} for vac in vacancies]
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