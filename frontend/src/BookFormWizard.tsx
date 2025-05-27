import React, { useState, useEffect } from 'react';
import {
  Paper, Box, Typography, Button, Stack, TextField, RadioGroup, FormControlLabel, Radio, Stepper, Step as MuiStep, StepLabel, Autocomplete, CircularProgress
} from '@mui/material';

const ANIMAL_OPTIONS = ['rabbit', 'fox', 'dog', 'cat', 'bear', 'lion', 'elephant', 'giraffe', 'tiger', 'monkey'];
const GENDER_OPTIONS = ['male', 'female'];
const SETTING_OPTIONS = ['Enchanted forest', 'Magical kingdom', 'Sunny meadow', 'Jungle', 'Ocean', 'Space', 'Farm', 'City park'];

// Wizard step types
const steps = [
  'Randomize',
  'Character Name',
  'Animal',
  'Gender',
  'Custom Elements',
  'Setting',
  'Summary',
];
type Step = 0 | 1 | 2 | 3 | 4 | 5 | 6;

interface FormState {
  randomizeAll: boolean;
  characterName: string;
  animal: string;
  gender: string;
  customElements: string;
  setting: string;
}

const initialForm: FormState = {
  randomizeAll: false,
  characterName: '',
  animal: '',
  gender: '',
  customElements: '',
  setting: '',
};

const progressMessages = [
  'Imagining a story...',
  'Coming up with the scenes...',
  'Thinking about the style...',
  'Drawing the pictures...',
  'Making the pages...',
  'Putting it all together...'
];

const API_BASE = process.env.REACT_APP_API_BASE_URL;

const BookFormWizard: React.FC = () => {
  const [step, setStep] = useState<Step>(0);
  const [form, setForm] = useState<FormState>(initialForm);
  const [errors, setErrors] = useState<{ [k: string]: string }>({});
  const [loading, setLoading] = useState(false);
  const [storyResult, setStoryResult] = useState<any>(null); // story, audio, session_id
  const [bookResult, setBookResult] = useState<any>(null); // book, illustrations, scenes
  const [progressStep, setProgressStep] = useState(0);

  useEffect(() => {
    let interval: NodeJS.Timeout | null = null;
    if (loading && !bookResult) {
      setProgressStep(0);
      interval = setInterval(() => {
        setProgressStep((prev) => prev < progressMessages.length ? prev + 1 : prev);
      }, 30000);
    }
    if (!loading || bookResult) {
      setProgressStep(0);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [loading, bookResult]);

  // Step navigation
  const next = () => setStep((s) => (s < steps.length - 1 ? ((s + 1) as Step) : s));
  const back = () => setStep((s) => (s > 0 ? ((s - 1) as Step) : s));

  // Handlers
  const handleRandomize = () => {
    setForm({ ...initialForm, randomizeAll: true });
    setStep(6);
  };
  const handleManual = () => {
    setForm({ ...form, randomizeAll: false });
    setStep(1);
  };
  const handleChange = (field: keyof FormState) => (e: any, value?: any) => {
    setForm((prev) => ({
      ...prev,
      [field]: value !== undefined ? value : e.target.value,
    }));
    setErrors((prev) => ({ ...prev, [field]: '' }));
  };
  const handleRadio = (field: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
    setErrors((prev) => ({ ...prev, [field]: '' }));
  };
  // Validation
  const validate = (): boolean => {
    let valid = true;
    const newErrors: { [k: string]: string } = {};
    if (step === 1 && !form.characterName.trim()) {
      newErrors.characterName = 'Please enter a name or type "random"';
      valid = false;
    }
    if (step === 2 && !form.animal.trim()) {
      newErrors.animal = 'Please select or type an animal';
      valid = false;
    }
    if (step === 3 && !form.gender.trim()) {
      newErrors.gender = 'Please select a gender';
      valid = false;
    }
    if (step === 5 && !form.setting.trim() && !form.customElements.trim()) {
      newErrors.setting = 'Please select or type a setting, or add special sauce';
      valid = false;
    }
    setErrors(newErrors);
    return valid;
  };
  const handleNext = () => {
    if (validate()) next();
  };

  // Two-step backend logic
  const handleCreateBook = async () => {
    setLoading(true);
    setStoryResult(null);
    setBookResult(null);
    try {
      // Step 1: Generate story and audio
      const payload: any = { randomize_all: form.randomizeAll };
      if (!form.randomizeAll) {
        if (form.characterName) payload.character_name = form.characterName;
        if (form.animal) payload.animal = form.animal;
        if (form.gender) payload.gender = form.gender;
        if (form.customElements) payload.custom_elements = form.customElements;
        if (form.setting) payload.setting = form.setting;
      }
      const storyRes = await fetch(`${API_BASE}/api/generate-story`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const storyData = await storyRes.json();
      setStoryResult(storyData);
      // Step 2: Generate book (illustrations, PDF) in background
      const bookRes = await fetch(`${API_BASE}/api/generate-book`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: storyData.session_id }),
      });
      const bookData = await bookRes.json();
      setBookResult(bookData);
    } catch (err: any) {
      setBookResult({ error: err.message || 'Unknown error' });
    } finally {
      setLoading(false);
    }
  };

  // Step content
  let content: React.ReactNode = null;
  if (loading && !bookResult) {
    // Show story if available, and book is still being generated
    content = (
      <Stack spacing={3} alignItems="center">
        <CircularProgress />
        <Typography variant="h6" color="text.primary">
          {progressStep < progressMessages.length
            ? progressMessages[progressStep]
            : 'Almost done...'}
        </Typography>
        {storyResult && (
          <>
            {storyResult.story && (
              <Box sx={{ maxWidth: 600, width: '100%', bgcolor: '#f9f9f9', p: 2, borderRadius: 2 }}>
                <Typography variant="h6" fontWeight={600} gutterBottom>Story</Typography>
                <Typography variant="body1" sx={{ whiteSpace: 'pre-line' }}>{storyResult.story}</Typography>
              </Box>
            )}
          </>
        )}
      </Stack>
    );
  } else if (bookResult) {
    content = (
      <Stack spacing={3} alignItems="center">
        {bookResult.error ? (
          <Typography color="error">{bookResult.error}</Typography>
        ) : (
          <>
            <Typography variant="h5" fontWeight={600} color="text.primary">Your Book is Ready!</Typography>
            {bookResult.book && (
              <a href={`${API_BASE}${bookResult.book}`} download style={{ textDecoration: 'none' }}>
                <Button variant="contained" color="primary">
                  Download PDF
                </Button>
              </a>
            )}
          </>
        )}
        <Button onClick={() => { setStoryResult(null); setBookResult(null); setStep(0); setForm(initialForm); }} sx={{ color: 'text.primary' }}>Create Another Book</Button>
      </Stack>
    );
  } else if (step === 0) {
    content = (
      <Stack spacing={3} alignItems="center">
        <Typography variant="h5" fontWeight={600} color="text.primary">
          Do you want a surprise story or create your own?
        </Typography>
        <Button variant="contained" color="primary" size="large" onClick={handleRandomize} sx={{ minWidth: 220 }}>
          Yes, surprise me!
        </Button>
        <Button variant="contained" color="primary" size="large" onClick={handleManual} sx={{ minWidth: 220 }}>
          Create my own
        </Button>
      </Stack>
    );
  } else if (step === 1) {
    content = (
      <Stack spacing={3} alignItems="center">
        <Typography variant="h6" color="text.primary">What is the main character's name?</Typography>
        <TextField
          label="Character Name"
          value={form.characterName}
          onChange={handleChange('characterName')}
          error={!!errors.characterName}
          helperText={errors.characterName || 'Leave blank or type "random" for a surprise!'}
          autoFocus
        />
        <Button variant="contained" onClick={handleNext}>Next</Button>
        <Button onClick={back} sx={{ color: 'text.primary' }}>Back</Button>
      </Stack>
    );
  } else if (step === 2) {
    content = (
      <Stack spacing={3} alignItems="center">
        <Typography variant="h6" color="text.primary">What kind of animal is the main character?</Typography>
        <Autocomplete
          options={ANIMAL_OPTIONS}
          value={form.animal}
          onChange={handleChange('animal')}
          freeSolo
          renderInput={(params) => (
            <TextField
              {...params}
              label="Animal"
              error={!!errors.animal}
              helperText={errors.animal || 'Pick from the list or type your own!'}
            />
          )}
        />
        <Button variant="contained" onClick={handleNext}>Next</Button>
        <Button onClick={back} sx={{ color: 'text.primary' }}>Back</Button>
      </Stack>
    );
  } else if (step === 3) {
    content = (
      <Stack spacing={3} alignItems="center">
        <Typography variant="h6" color="text.primary">What is the main character's gender?</Typography>
        <RadioGroup row value={form.gender} onChange={handleRadio('gender')}>
          {GENDER_OPTIONS.map((g) => (
            <FormControlLabel key={g} value={g} control={<Radio />} label={g.charAt(0).toUpperCase() + g.slice(1)} />
          ))}
        </RadioGroup>
        {errors.gender && <Typography color="error">{errors.gender}</Typography>}
        <Button variant="contained" onClick={handleNext}>Next</Button>
        <Button onClick={back} sx={{ color: 'text.primary' }}>Back</Button>
      </Stack>
    );
  } else if (step === 4) {
    content = (
      <Stack spacing={3} alignItems="center">
        <Typography variant="h6" color="text.primary">Do you want to add special sauce?</Typography>
        <TextField
          label="Special sauce (optional)"
          value={form.customElements}
          onChange={handleChange('customElements')}
          multiline
          minRows={2}
          helperText="E.g., 'a story about being a kind and helpful older sibling'"
        />
        <Button variant="contained" onClick={handleNext}>Next</Button>
        <Button onClick={back} sx={{ color: 'text.primary' }}>Back</Button>
      </Stack>
    );
  } else if (step === 5) {
    content = (
      <Stack spacing={3} alignItems="center">
        <Typography variant="h6" color="text.primary">Where does the story take place?</Typography>
        <Autocomplete
          options={SETTING_OPTIONS}
          value={form.setting}
          onChange={handleChange('setting')}
          freeSolo
          renderInput={(params) => (
            <TextField
              {...params}
              label="Setting"
              error={!!errors.setting}
              helperText={errors.setting || 'Pick from the list or type your own!'}
            />
          )}
        />
        <Button variant="contained" onClick={handleNext}>Next</Button>
        <Button onClick={back} sx={{ color: 'text.primary' }}>Back</Button>
      </Stack>
    );
  } else if (step === 6) {
    content = (
      <Stack spacing={3} alignItems="center">
        <Typography variant="h5" fontWeight={600} color="text.primary">Ingredients</Typography>
        <Box>
          {form.randomizeAll ? (
            <Typography>Random</Typography>
          ) : (
            <>
              <Typography><b>Character Name:</b> {form.characterName || '(random)'}</Typography>
              <Typography><b>Animal:</b> {form.animal || '(random)'}</Typography>
              <Typography><b>Gender:</b> {form.gender || '(random)'}</Typography>
              <Typography><b>Special sauce:</b> {form.customElements || '(none)'}</Typography>
              <Typography><b>Setting:</b> {form.setting || '(random)'}</Typography>
            </>
          )}
        </Box>
        <Button variant="contained" color="primary" size="large" onClick={handleCreateBook}>
          Create book
        </Button>
        <Button onClick={back} sx={{ color: 'text.primary' }}>Back</Button>
      </Stack>
    );
  }

  return (
    <Paper elevation={3} sx={{ p: 4 }}>
      <Stepper activeStep={step} alternativeLabel sx={{ mb: 4 }}>
        {steps.map((label) => (
          <MuiStep key={label}>
            <StepLabel>{label}</StepLabel>
          </MuiStep>
        ))}
      </Stepper>
      <Box>
        {content}
      </Box>
    </Paper>
  );
};

export default BookFormWizard; 