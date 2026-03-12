from fpdf import FPDF
import os

class InvoicePDF(FPDF):
    def header(self):
        self.set_font('helvetica', 'B', 15)
        self.cell(80)
        self.cell(30, 10, 'RECHNUNG', 0, 0, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.cell(0, 10, f'Seite {self.page_no()}/{{nb}}', 0, 0, 'C')

def generate_invoice():
    pdf = InvoicePDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font('helvetica', '', 12)

    # Sender
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 5, 'GartenProfi GmbH | Blumenweg 10 | 12345 Berlin', 0, 1)
    pdf.ln(5)

    # Recipient
    pdf.set_font('helvetica', '', 12)
    pdf.cell(0, 5, 'Muster Hausverwaltung GmbH', 0, 1)
    pdf.cell(0, 5, 'Z.Hd. Herr Schmidt', 0, 1)
    pdf.cell(0, 5, 'Musterstraße 1', 0, 1)
    pdf.cell(0, 5, '12345 Berlin', 0, 1)
    pdf.ln(15)

    # Invoice Details
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, 'Rechnungsnummer: RE-2026-001', 0, 1)
    pdf.set_font('helvetica', '', 12)
    pdf.cell(0, 5, 'Rechnungsdatum: 12.03.2026', 0, 1)
    pdf.cell(0, 5, 'Leistungszeitraum: 01.01.2025 - 31.12.2025', 0, 1)
    pdf.ln(10)

    # Subject
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 5, 'Betreff: Brennstofflieferung (Erdgas Brennwert) für das Gesamtobjekt', 0, 1)
    pdf.ln(5)
    pdf.set_font('helvetica', '', 12)
    pdf.multi_cell(0, 5, 'Hiermit stellen wir Ihnen die Kosten für die Lieferung von Erdgas (Brennwert) für das Mehrfamilienhaus Musterstraße 1 für das Jahr 2025 in Rechnung. Diese Kosten sind gemäß Betriebskostenverordnung (BetrKV) zur Umlage auf die Mieter geeignet.')
    pdf.ln(10)

    # Table Header
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(100, 10, 'Position', 1, 0, 'C', 1)
    pdf.cell(40, 10, 'Betrag (Netto)', 1, 0, 'C', 1)
    pdf.cell(50, 10, 'Gesamt', 1, 1, 'C', 1)

    # Table Content
    pdf.cell(100, 10, 'Erdgaslieferung (Brennwert)', 1)
    pdf.cell(40, 10, '1.000,00 EUR', 1, 0, 'R')
    pdf.cell(50, 10, '1.000,00 EUR', 1, 1, 'R')

    pdf.ln(5)

    # Summary
    pdf.cell(140, 10, 'Zwischensumme (Netto):', 0, 0, 'R')
    pdf.cell(50, 10, '1.000,00 EUR', 0, 1, 'R')
    pdf.cell(140, 10, 'Umsatzsteuer (19%):', 0, 0, 'R')
    pdf.cell(50, 10, '190,00 EUR', 0, 1, 'R')
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(140, 10, 'Rechnungsbetrag (Brutto):', 0, 0, 'R')
    pdf.cell(50, 10, '1.190,00 EUR', 0, 1, 'R')

    pdf.ln(15)
    pdf.set_font('helvetica', '', 12)
    pdf.cell(0, 5, 'Zahlbar ohne Abzug bis zum 26.03.2026.', 0, 1)
    pdf.cell(0, 5, 'Bitte geben Sie bei der Überweisung die Rechnungsnummer an.', 0, 1)

    pdf.ln(20)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 5, 'GartenProfi GmbH | IBAN: DE12 3456 7890 1234 5678 90 | BIC: GENODEM1XXX', 0, 1)
    pdf.cell(0, 5, 'USt-ID: DE987654321 | Geschäftsführer: Peter Gärtner', 0, 1)

    output_path = "valid_invoice.pdf"
    pdf.output(output_path)
    print(f"Invoice generated: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    generate_invoice()
