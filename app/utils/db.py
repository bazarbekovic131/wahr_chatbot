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
                        phone VARCHAR(16) UNIQUE NOT NULL,
                        age VARCHAR(32),
                        production_experience VARCHAR(32),
                        completed_survey BOOLEAN,
                        name VARCHAR(50),
                        vacancy VARCHAR(32),
                        sent BOOLEAN DEFAULT FALSE,
                        resume VARCHAR(32) DEFAULT 'Не указан'
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
        
        if user is None:
            return False
        return True
    
    def create_user(self, phone):
        with self.conn.cursor() as cur:
            try:
                cur.execute("INSERT INTO users (phone) VALUES (%s) ON CONFLICT (phone) DO NOTHING", (phone,))
                cur.execute("INSERT INTO surveys (phone, completed_survey) VALUES (%s, FALSE) ON CONFLICT (phone) DO NOTHING", (phone,))
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
                """.format(key=key), (text, phone,)
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

    def save_vacancy(self, phone, vacancy_name):
        with self.conn.cursor() as cur:
            # First try to update the record
            cur.execute(
                """
                UPDATE surveys SET 
                vacancy = %s
                WHERE phone = %s;
                """, (vacancy_name, phone,)
            )

            if cur.rowcount == 0:
                # If no rows were updated, insert a new record
                cur.execute(
                    """
                    INSERT INTO surveys (phone, vacancy)
                    VALUES (%s, %s)
                    """, (phone, vacancy_name,)
                )

            # Commit the transaction
            self.conn.commit()
    def vacancy_filled(self, phone):
        with self.conn.cursor() as cur:
            cur.execute("SELECT vacancy FROM surveys WHERE phone = %s", (phone,))
            result = cur.fetchone()
            return result is not None
        
    def has_completed_survey(self, phone):
        with self.conn.cursor() as cur:
            cur.execute("SELECT has_completed_survey FROM users WHERE phone = %s", (phone,))
            result = cur.fetchone()
            return result[0]
        
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
            cur.execute("UPDATE users SET current_step = current_step + 1 WHERE phone = %s;", (phone,))
            self.conn.commit()

    def set_step(self, phone):
        with self.conn.cursor() as cur:
            cur.execute("UPDATE users SET current_step =  1 WHERE phone = %s;", (phone,))
            self.conn.commit()

    def set_survey_mode(self, phone, value):
        ''' value is True or False'''
        with self.conn.cursor() as cur:
            cur.execute("UPDATE users SET survey_mode = %s WHERE phone = %s;", (value, phone,))
            self.conn.commit()  # Commit the transaction            

    def mark_survey_as_completed_or_incompleted(self, phone, isCompleted):
        ''' value is True or False'''
        with self.conn.cursor() as cur:
            cur.execute("UPDATE users SET has_completed_survey = %s WHERE phone = %s;", (isCompleted, phone,))
            cur.execute("UPDATE surveys SET completed_survey = %s WHERE phone = %s;", (isCompleted, phone,))
            self.conn.commit()  # Commit the transaction 

    ######## VACANCIES ##############

    def get_vacancies(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id, title FROM vacancies")
            return cursor.fetchall()
        
    def get_vacancies_with_details(self):
        with self.conn.cursor() as cursor:
            cursor.execute("SELECT id, title, salary FROM vacancies")
            return cursor.fetchall()

    def get_vacancy_details(self, vacancy_id):
        '''
            used in forming the interactive message
        '''

        with self.conn.cursor() as cursor:
            cursor.execute("SELECT title, requirements, details, tasks, salary FROM vacancies WHERE id=%s", (vacancy_id,))
            df = cursor.fetchone()
            return df
        
    def get_vacancies_for_interactive_message(self):
        vacancies = self.get_vacancies_with_details()
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

        sections = []
        max_rows_per_section = 10
        for i in range(0, len(vacancies), max_rows_per_section):
            section_vacancies = vacancies[i:i + max_rows_per_section]
            section = {
                "title": f"Стр. {i // max_rows_per_section + 1}",
                "rows": [{"id": str(vac[0]), "title": shorten_title(vac[1]), "description": vac[2]} for vac in section_vacancies]
            }
            sections.append(section)
        
        return sections

    # new ones. untested
    def get_incomplete_surveys(self):
        with self.conn.cursor() as cur:
            query = 'SELECT * FROM surveys WHERE sent = FALSE;'
            cur.execute(query)
            df = cur.fetchall()
        self.conn.commit()
        return pd.DataFrame(df, columns=['id', 'phone', 'age','sent', 'name', 'completed_survey', 'production_experience', 'resume', 'vacancy'])

    def update_sent_status(self, survey_id):
        query = """
            UPDATE surveys SET sent = TRUE WHERE id = %s;
        """
        self.conn.cursor().execute(query, (survey_id,))
        self.conn.commit()